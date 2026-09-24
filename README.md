# MCP Agent Security Benchmark — Harness

Code for the orchestrator, mock scenario servers, and trace-based scorer
described in Sections 5.5 and 6.3 of the paper. This fills in the "not yet
run" cells in Tables 2/3 (Section 7).

## Layout

```
harness/
  harness/
    orchestrator.py   # agent loop (Anthropic + OpenAI-compatible providers) over MCP stdio
    scenarios.py       # scenario registry: server + benign task + scorer per ID
    scorer.py          # attack_success / task_success checkers, ASR/TSR aggregation
    trace_logger.py     # structured per-run JSONL trace writer
  servers/
    t1_tier1_filesystem_server.py        # already run (Table 2/3)
    t2_tier1_filesystem_server.py        # already run
    t3_tier1_desktop_commander_server.py # already run
    t1_tier2_jupyter_server.py           # NEW — obfuscated data siphon
    t2_tier2_fetch_server.py             # NEW — synonym-obfuscated injection
    t3_tier2_filesystem_server.py        # NEW — path traversal
  run_benchmark.py     # CLI entry point
```

## Setup

```bash
pip install mcp anthropic openai --break-system-packages
export GOOGLE_API_KEY=...        # Gemini Flash-Lite (OpenAI-compatible endpoint)
export OPENROUTER_API_KEY=...    # Nemotron-3-Super (via OpenRouter)
```

Model slugs are verified as of 2026-07-18: Gemini uses
`gemini-3.1-flash-lite` against `https://generativelanguage.googleapis.com/v1beta/openai/`,
and Nemotron-3-Super's free-tier OpenRouter slug is
`nvidia/nemotron-3-super-120b-a12b:free` against `https://openrouter.ai/api/v1`
(both already set in `run_benchmark.py`). These strings can still drift over
time — worth a quick recheck against each provider's current docs if you're
running this a while after the above date.

Three more models were added on 2026-07-23, all also via OpenRouter (same
`OPENROUTER_API_KEY`, verified against OpenRouter's model pages that day):

| `--model` key                | Model                          | slug                                      |
|-------------------------------|---------------------------------|--------------------------------------------|
| `hy3-preview`                  | Tencent: Hy3 preview            | `tencent/hy3-preview:free`                  |
| `llama-3.3-70b-openrouter`     | Meta: Llama 3.3 70B Instruct    | `meta-llama/llama-3.3-70b-instruct:free`    |
| `gpt-oss-20b`                  | OpenAI: gpt-oss-20b (free)      | `openai/gpt-oss-20b:free`                   |

**Quota note:** these three plus `nemotron-3-super` all share one
OpenRouter account's daily free-tier quota (50 req/day unfunded) — it is
*not* 50 per model. Running all four in one day means splitting one shared
budget four ways, so always use `--resume` (see below) and expect to spread
a full roster across several days unless the OpenRouter account is funded
with $10+ to raise the cap.

## Running the new Tier-2 scenarios

```bash
# T1-Tier2, T2-Tier2, T3-Tier2 against Gemini Flash-Lite, n=15 each
python run_benchmark.py --scenario T1-Tier2 --model gemini-flash-lite --n 15
python run_benchmark.py --scenario T2-Tier2 --model gemini-flash-lite --n 15
python run_benchmark.py --scenario T3-Tier2 --model gemini-flash-lite --n 15

# Same three against Nemotron-3-Super
python run_benchmark.py --scenario T1-Tier2 --model nemotron-3-super --n 15
python run_benchmark.py --scenario T2-Tier2 --model nemotron-3-super --n 15
python run_benchmark.py --scenario T3-Tier2 --model nemotron-3-super --n 15

# Also bring Nemotron up to n>=15 on the one un-run Tier-1 cell:
python run_benchmark.py --scenario T1-Tier1 --model nemotron-3-super --n 15
```

Each command prints a JSON summary (`n`, `asr`, `tsr`) you can drop straight
into Table 2 / Table 3. Raw per-trial traces land in `./traces/<scenario_id>.jsonl`,
and each trial's pass/fail score is separately persisted to
`./traces/<scenario_id>.scores.jsonl` (this is what makes `--resume` possible —
see below). The raw traces are also what you'll pull the two trace-excerpt
examples from for Section 8 (Discussion).

## Resuming an interrupted or rate-limited run

Free-tier rate limits (especially on OpenRouter/Nemotron) mean a `--n 15` run
often won't finish in one pass. Add `--resume` and it'll count how many
already-scored trials exist on disk for that exact scenario+model pair, and
only run the shortfall instead of starting over from zero:

```bash
python run_benchmark.py --scenario T2-Tier1 --model nemotron-3-super --n 15 --resume
```

If 8 are already on disk, this runs 7 more and reports the cumulative total
(`n=15`, not `n=7`). Without `--resume`, each run is independent and reports
only that invocation's own trials — scores still get appended to the same
`.scores.jsonl` file either way, so nothing is ever lost; `--resume` just
decides what the *summary* reports and how many *new* trials get attempted.

## Honest gaps in this code, so you don't get surprised mid-run

- **`task_checker_factory` is a stub (`always True`) for every scenario.**
  The paper's task-success axis needs real grading — did the agent actually
  produce a correct summary / correct total / correct file listing — which
  is either an LLM-as-judge call or manual transcript review, not something
  a file-existence check can do. Wire this in before trusting the TSR column
  for new scenarios; it's fine as-is only because the Tier-1 TSR numbers
  already in the paper were graded separately, not by this stub.
- **Rate limits.** Section 9 already documents that free-tier rate limits
  capped Nemotron's `n`. `run_benchmark.py` has no backoff/retry logic —
  add it (or just re-run failed trials) rather than assuming 15/15 will
  succeed in one pass.
- **`nemotron-3-super`'s `model_id`** (`nvidia/nemotron-3-super-120b-a12b:free`)
  is verified against OpenRouter as of 2026-07-18 — but re-check before a
  run if it's been a while, since free-tier slugs occasionally get renamed
  or retired.
- **The T2-Tier2 scenario's `fetch_url` ignores the `url` argument** and
  always returns the same fixed article — that's intentional (it isolates
  the injection variable) but worth knowing if you extend it.
- **No sandbox network isolation is enforced by this code itself** — it
  relies on you running it inside the same network-isolated sandbox
  described in Section 5.3. The servers don't make outbound calls, but
  nothing here stops a future scenario script from adding one by mistake.
