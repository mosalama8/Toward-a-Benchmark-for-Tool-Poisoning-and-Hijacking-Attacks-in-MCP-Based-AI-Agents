# Toward-a-Benchmark-for-Tool-Poisoning-and-Hijacking-Attacks-in-MCP-Based-AI-Agents

# MCP Agent Security Benchmark

This repo contains the paper, the benchmark harness, the raw experiment
data, and the scoring pipeline behind **"Toward a Benchmark for
Tool-Poisoning and Hijacking Attacks in MCP-Based AI Agents"**
(Mohamed Salama, Dept. of Computer Systems Engineering, October
University for Modern Sciences and Arts).

This file is the map of the whole project: what everything is, how the
pieces fit together, and the exact commands to reproduce or extend any
part of it. It supersedes `harness/README.md` (kept in place, but that
file is now the narrower "adding new Tier-2 scenarios" note it started
as — this file is the current source of truth for what actually exists
and how to run it).

---

## 1. What's in this repo

```
mcp-security-benchmark/
├── MCP_Agent_Security_Benchmark_v2.docx   # the paper (corrected version)
└── harness/
    ├── README.md                          # narrower, partly superseded — see note above
    ├── run_benchmark.py                   # CLI: run N live trials of one scenario x one model
    ├── run_new_models.ps1                 # batch-runs a whole model across every scenario
    ├── test-groq.ps1                      # one-off smoke test for a Groq model endpoint
    ├── harness/                           # the library code (imported by run_benchmark.py)
    │   ├── orchestrator.py                # the agent loop itself (talks to the LLM + MCP servers)
    │   ├── scenarios.py                   # registry of all 14 scenarios: server, task, checkers
    │   ├── scorer.py                      # Attack Success scoring + ScoreWriter/--resume bookkeeping
    │   ├── task_checkers.py               # REAL Task Success checkers (retroactive, trace-only)
    │   ├── rescore_task_success.py        # re-derives Table 4 from raw traces using task_checkers.py
    │   └── trace_logger.py                # writes one JSONL event stream per trial
    ├── servers/                           # the 20 mock MCP servers (one or more per scenario)
    ├── sandbox_*/                         # leftover fixture data from manual/standalone server runs
    │                                       # (NOT used by the harness itself — see §6)
    ├── traces/                            # raw per-trial data: <ScenarioID>.jsonl + .scores.jsonl
    └── scoring_output/                    # rescore_task_success.py's output
        ├── table4_results.json            # clean, Table-4-shaped aggregate (n, count, rate, means)
        └── task_success_detail.json       # per-trial pass/fail + reason, for every one of 1,070 trials
```

## 2. The one thing to understand before running anything

**There are two separate, non-overlapping things you can do with this
code, and they use different scoring paths:**

| | Collects new data? | Uses | Task Success is... |
|---|---|---|---|
| **A. Run new live trials** (`run_benchmark.py`) | ✅ yes — calls a real model, costs quota | `scenarios.py`'s `task_checker_factory` | **always `True` — it's a stub.** Attack Success is real; Task Success is not. |
| **B. Re-score existing traces** (`rescore_task_success.py`) | ❌ no — pure re-computation over files already on disk | `task_checkers.py` (14 real, scenario-specific checkers) | **real** — this is what Table 4 in the paper actually reports |

This is easy to miss because both paths are "the scorer" in casual
conversation, but they are different code with different correctness.
`task_checkers.py` was added specifically to grade the trace corpus
*after the fact*; nobody wired it back into `scenarios.py`, so a fresh
`run_benchmark.py` invocation today will still print `task_success:
True` for every single trial regardless of what actually happened.
That's fine for Attack Success work (extending the corpus, testing a new
scenario against a new model) but **do not trust a live run's own
`tsr` field** — if you need a real Task Success number for a scenario,
run it, then re-score with `rescore_task_success.py` (or write a new
checker function in `task_checkers.py` if the scenario is new — see §5).

## 3. Setup

```bash
pip install mcp anthropic openai --break-system-packages
```

Environment variables, one per provider you intend to use (only set the
ones you need):

```bash
export GOOGLE_API_KEY=...        # Gemini Flash-Lite
export OPENROUTER_API_KEY=...    # Nemotron-3-Super, Hy3 preview, Llama-3.3-70B (OpenRouter), gpt-oss-20b
export GROQ_API_KEY=...          # Llama-3.3-70B (Groq), gpt-oss-120b (Groq)
export CEREBRAS_API_KEY=...      # Llama-3.3-70B (Cerebras)
export ANTHROPIC_API_KEY=...     # reserved for a future frontier-tier config (not yet added)
```

`run_benchmark.py` checks the relevant variable up front and exits with
a clear message (not a mid-run traceback) if it's missing.

**Quota gotcha:** `nemotron-3-super`, `hy3-preview`,
`llama-3.3-70b-openrouter`, and `gpt-oss-20b` all share **one**
OpenRouter account's daily free-tier pool (50 req/day unfunded — not 50
per model). Budget trials across all four together, always pass
`--resume`, and expect to spread a full roster over several days unless
the account is funded ($10+ raises the cap). Groq (~1,000 req/day/model)
and Cerebras (~1M tokens/day, 30 RPM, no card required) are separate
pools from OpenRouter and from each other.

**Model slugs drift.** Every slug in `run_benchmark.py` was verified
against the provider's own docs/model pages on a specific date (comments
above `MODEL_CONFIGS` record which date for which model). `gpt-oss-120b`
on Groq is flagged **UNVERIFIED** — its data already exists in the trace
corpus, but the config entry was reconstructed by guessing Groq's naming
convention, not confirmed against Groq's docs. Recheck before relying on
it for a new run.

## 4. Running new trials

Every provider is OpenAI-compatible under the hood, so adding a model
never requires touching `orchestrator.py` — just add a `ModelConfig`
entry in `run_benchmark.py`.

```bash
cd harness

# One scenario, one model, 15 fresh trials:
python run_benchmark.py --scenario T1-Tier2 --model gemini-flash-lite --n 15

# Same, but resume: only runs the shortfall if some trials already exist
# on disk for this exact scenario+model+config combination:
python run_benchmark.py --scenario T2-Tier1 --model nemotron-3-super --n 15 --resume

# Batch: every remaining scenario against two Groq/OpenRouter models —
# this is exactly what run_new_models.ps1 automates:
./run_new_models.ps1
```

**Scenario IDs** (14 total, matching Table 1b in the paper):
`T1-Tier1`, `T2-Tier1`, `T3-Tier1`, `T1-Tier2`, `T2-Tier2`, `T3-Tier2`,
`T4-Tier2`, `T2-Tier3`, `T3-Tier3`, `T4-Tier3`, `T5-Tier3`, `T5-Tier4`,
`T6-Tier4`, `TBD-Tier5`.

**Model keys:** `gemini-flash-lite`, `nemotron-3-super`, `hy3-preview`,
`llama-3.3-70b-openrouter`, `gpt-oss-20b`, `llama-3.3-70b-groq`,
`llama-3.3-70b-cerebras`, `gpt-oss-120b-groq` — plus a `-safety` variant
of each of the four models used in the safety-prompt experiment
(`nemotron-3-super-safety`, `llama-3.3-70b-groq-safety`,
`gpt-oss-20b-safety`, `gpt-oss-120b-groq-safety`), which are identical to
their default sibling except for one extra system prompt instructing the
model to treat tool output as untrusted (see the `SAFETY_PROMPT_TEXT`
constant in `run_benchmark.py` for the exact wording under test).

Output: a JSON summary (`n`, `asr`, `tsr` — remember `tsr` here is
meaningless, per §2) printed to stdout; raw per-trial events land in
`traces/<scenario_id>.jsonl`; each trial's pass/fail lands in
`traces/<scenario_id>.scores.jsonl` (this second file is what makes
`--resume` possible — it's read back to count already-completed trials
without re-parsing every raw trace).

**`test-groq.ps1`** is not part of the pipeline — it's a two-line smoke
test to confirm a Groq API key and model string actually work before
spending trial budget on a full run.

## 5. Getting a real Task Success number (Table 4)

This is a **separate step**, run after trials are already collected:

```bash
cd harness/harness
python3 rescore_task_success.py
```

It reads every `traces/<ScenarioID>.jsonl` file, applies that scenario's
real checker from `task_checkers.py` (one function per scenario — checks
things like "was `run_cell` called and does the final answer contain the
correct total" or "were all three required batches processed"), and
writes:

- **`scoring_output/table4_results.json`** — per-scenario, per-model `n` /
  success count / success rate, plus the four canonical-model means. This
  is Table 4 exactly as it appears in the paper.
- **`scoring_output/task_success_detail.json`** — one row per trial
  (1,070 total) with a machine-readable pass/fail reason, so any single
  cell in Table 4 traces back to specific, inspectable trials rather than
  being taken on faith.

It also prints a full per-scenario/per-model table to stdout, including
rows for models **not** in the canonical five — those are flagged inline
(`(excluded from Table 4 — see notes)`) rather than silently dropped, so
nothing looks hidden. The canonical set is:

```
Gemini Flash-Lite, Nemotron-3-Super, Llama 3.3 70B (Groq),
OpenAI: gpt-oss-20b (free), OpenAI: gpt-oss-120b (Groq)
```

Excluded rows are: single-trial provider-label variants, one abandoned
DeepSeek run, and one mislabeled duplicate trial.

**This script is deterministic and does not call any model API** — it's
a pure function over already-recorded trace events. Re-running it always
produces byte-identical output (verified across three separate runs,
including after two bug fixes to the script itself). This is also what
makes it a genuine independent verification path: anyone can unzip this
repo, run this one command, and get the same 70 table cells and the same
four means the paper reports, traceable cell-by-cell back to raw trial
data — no re-running of live model calls required, and nothing taken on
the original scoring's word.

**Adding a checker for a new scenario:** write a function in
`task_checkers.py` with the signature `(events: list[dict]) -> (bool,
str)` — inspect `tool_call` / `tool_result` / `model_text` /
`session_boundary` events only (sandbox filesystem state no longer
exists by the time you're re-scoring), return `(True/False, reason)`,
and add it to the `CHECKERS` dict at the bottom of the file.

## 6. The `sandbox_*` directories

These are **not** used by the harness during a real run.
`scenarios.py`'s `prepare_sandbox()` always creates a fresh temp
directory (`tempfile.mkdtemp`) per trial and passes it to the server via
the `MCP_SANDBOX_DIR` environment variable; it's cleaned up automatically
afterward. Each server script does default to a matching
`./sandbox_<scenario_id>/` path when `MCP_SANDBOX_DIR` isn't set — which
is what these checked-in folders are: leftovers from someone running a
server script directly (outside the harness) at some point, not live
state. They're useful as a quick look at what a scenario's fixture data
looks like (e.g. `sandbox_t2_tier1/notes.txt` contains the actual
injected instruction text for that scenario) but you can delete them
without affecting anything. The embedded "secrets" in them
(`sk-sandbox-do-not-exfiltrate`, etc.) are fake, sandbox-only values used
to detect exfiltration — not real credentials.

## 7. Honest gaps and gotchas

- **Live-run Task Success is a stub (§2).** Fixed at the scoring level
  via `rescore_task_success.py`, not at the source — `scenarios.py`
  itself was never updated, so this will keep surprising you on every
  new live run until someone wires `task_checkers.py` into
  `task_checker_factory` directly.
- **No retry/backoff logic.** Free-tier rate limits (especially
  OpenRouter/Nemotron) mean a `--n 15` run often won't finish in one
  pass. Re-run with `--resume` rather than expecting 15/15 in one go.
- **`gpt-oss-120b-groq`'s model ID is unverified** — see §3.
- **`T2-Tier2`'s `fetch_url` ignores its `url` argument** and always
  returns the same fixed article. Intentional (isolates the injection
  variable as the only difference between trials), but worth knowing if
  you extend the scenario.
- **No sandbox network isolation is enforced by the code itself** — it
  relies on you already running inside a network-isolated environment.
  The mock servers don't make outbound calls, but nothing stops a future
  scenario script from adding one by mistake.
- **A frontier/paid-tier model was never evaluated** (project budget) —
  this is a headline limitation of the paper, not a code gap, but if you
  add one, uncomment and fill in the `frontier-default` template in
  `run_benchmark.py`'s `MODEL_CONFIGS`.
- **The stratified real-server sampling procedure** (extending the
  corpus beyond synthetic servers to real, publicly available MCP
  servers) is designed in the paper (Section 6.2) but has no
  corresponding code in this repo yet.

## 8. Quick reference: full reproduction from a clean checkout

```bash
# 1. Install deps
pip install mcp anthropic openai --break-system-packages

# 2. (Optional) collect more trial data — needs API keys, costs quota
cd harness
python run_benchmark.py --scenario T1-Tier1 --model gemini-flash-lite --n 15 --resume

# 3. Regenerate Table 4 from whatever's in traces/ (no API calls, no quota,
#    fully deterministic — this is the step that matters for verifying
#    the paper's numbers)
cd harness
python3 rescore_task_success.py
```
