import json, sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).parent))
from task_checkers import CHECKERS

# Portable: traces/ lives alongside harness/ at the repo root, regardless of
# where this checkout is cloned.
TRACE_DIR = Path(__file__).resolve().parent.parent / "traces"

# Canonical five-model corpus Table 4 reports over (Section 7.2/7.6). Rows for
# any other model label (single-trial provider variants, abandoned runs, a
# mislabeled duplicate under a bare "gpt-oss-20b" tag -- see Section 9) are
# still scored and logged to detail output, but excluded from the aggregate
# table/JSON so a rerun doesn't produce extra unexplained rows.
CANONICAL_MODELS = {
    "Gemini Flash-Lite",
    "Nemotron-3-Super",
    "Llama 3.3 70B (Groq)",
    "OpenAI: gpt-oss-20b (free)",
    "OpenAI: gpt-oss-120b (Groq)",
}


def get_config(row):
    for e in row.get("events", []):
        if e.get("event_type") == "session_start":
            cfg = e.get("payload", {}).get("config")
            if cfg:
                return cfg
    # Fallback: a handful of early trials have no session_start event at all
    # (see audit note below), so their config only lives on the trace record
    # itself. Checking this first would be simpler, but session_start (when
    # present) reflects what the harness actually did at runtime, so it takes
    # priority; this is only a fallback for records that lack it entirely.
    return row.get("config") or "default"

results = {}  # scenario -> model -> list of (bool, reason)
detail_log = []

for scenario_id, checker in CHECKERS.items():
    fpath = TRACE_DIR / f"{scenario_id}.jsonl"
    if not fpath.exists():
        print(f"MISSING trace file for {scenario_id}", file=sys.stderr)
        continue
    rows = []
    with fpath.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append(r)

    results[scenario_id] = {}
    for model, model_rows in by_model.items():
        default_rows = [r for r in model_rows if get_config(r) == "default"]
        default_rows.sort(key=lambda r: r.get("started_at", 0))
        default_rows = default_rows[:15]  # matches Table 3's n=15 methodology (validated in 8.8.8)
        scored = []
        for r in default_rows:
            ok, reason = checker(r["events"])
            scored.append((ok, reason, r["run_id"]))
            detail_log.append({
                "scenario_id": scenario_id, "model": model, "run_id": r["run_id"],
                "task_success": ok, "reason": reason,
            })
        results[scenario_id][model] = scored

# Print per-scenario, per-model n and TSR -- every model found, canonical or
# not, so a non-canonical row (single-trial provider variant, abandoned
# DeepSeek run, the mislabeled duplicate) is visible rather than silently
# dropped from the console output.
print(f"{'Scenario':<12}{'Model':<32}{'n':<5}{'TSR':<8}")
for scenario_id in CHECKERS:
    if scenario_id not in results:
        continue
    for model, scored in sorted(results[scenario_id].items()):
        n = len(scored)
        tsr = 100.0 * sum(1 for ok, _, _ in scored if ok) / n if n else float("nan")
        flag = "" if model in CANONICAL_MODELS else "  (excluded from Table 4 -- see notes)"
        print(f"{scenario_id:<12}{model:<32}{n:<5}{tsr:<8.1f}{flag}")

OUT_DIR = Path(__file__).resolve().parent.parent / "scoring_output"
OUT_DIR.mkdir(exist_ok=True)

# Clean, Table-4-shaped aggregate: canonical five-model corpus only.
table4 = {}
for scenario_id in CHECKERS:
    if scenario_id not in results:
        continue
    table4[scenario_id] = {}
    for model, scored in results[scenario_id].items():
        if model not in CANONICAL_MODELS:
            continue
        n = len(scored)
        succ = sum(1 for ok, _, _ in scored if ok)
        table4[scenario_id][model] = {
            "n": n,
            "task_success_count": succ,
            "task_success_rate_pct": round(100.0 * succ / n, 1) if n else None,
        }

means = {}
for model in CANONICAL_MODELS:
    vals = [table4[s][model]["task_success_rate_pct"] for s in table4 if model in table4[s]]
    if vals:
        means[model] = round(sum(vals) / len(vals), 1)

with open(OUT_DIR / "table4_results.json", "w") as f:
    json.dump({
        "description": "Table 4 (Task Utility Retention) recomputed from raw trace "
                        "files via task_checkers.py, canonical 5-model corpus only.",
        "per_scenario": table4,
        "mean_by_model": means,
    }, f, indent=2)

with open(OUT_DIR / "task_success_detail.json", "w") as f:
    json.dump(detail_log, f, indent=2)

print(f"\nWrote {sum(len(v) for v in table4.values())} table cells to "
      f"scoring_output/table4_results.json", file=sys.stderr)
print(f"Wrote {len(detail_log)} detail rows to "
      f"scoring_output/task_success_detail.json", file=sys.stderr)
