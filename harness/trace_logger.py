"""
trace_logger.py

Structured, per-run JSONL trace logging for the MCP agent-security benchmark.

Every tool call the agent makes (name, parameters, server response, and the
agent's eventual text output) is appended to a single JSONL file per run.
The scorer (scorer.py) consumes these files to compute Attack Success and
Task Success independently.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class TraceEvent:
    ts: float
    event_type: str            # "task_start" | "tool_call" | "tool_result" | "model_text" | "task_end"
    payload: dict[str, Any]


@dataclass
class RunTrace:
    run_id: str
    scenario_id: str
    model: str
    started_at: float
    config: str = "default"  # "default" | "safety_prompted"
    events: list[TraceEvent] = field(default_factory=list)
    ended_at: float | None = None

    def log(self, event_type: str, **payload: Any) -> None:
        self.events.append(TraceEvent(ts=time.time(), event_type=event_type, payload=payload))

    def log_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self.log("tool_call", tool_name=tool_name, arguments=arguments)

    def log_tool_result(self, tool_name: str, result: Any, is_error: bool = False) -> None:
        self.log("tool_result", tool_name=tool_name, result=_safe_str(result), is_error=is_error)

    def log_model_text(self, text: str) -> None:
        self.log("model_text", text=text)

    def finish(self) -> None:
        self.ended_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _safe_str(value: Any, limit: int = 20_000) -> str:
    """MCP tool results can be large or non-JSON-serializable; coerce safely."""
    try:
        s = value if isinstance(value, str) else json.dumps(value, default=str)
    except Exception:
        s = repr(value)
    return s[:limit]


class TraceWriter:
    """
    One TraceWriter per scenario. Each run gets its own line in a JSONL file
    at <output_dir>/<scenario_id>.jsonl, so trials can be appended incrementally
    without re-reading the whole file, and partial runs (crashes) don't corrupt
    earlier trials.
    """

    def __init__(self, output_dir: str | Path, scenario_id: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scenario_id = scenario_id
        self.path = self.output_dir / f"{scenario_id}.jsonl"

    def new_run(self, model: str, config: str = "default") -> RunTrace:
        run_id = f"{self.scenario_id}-{model}-{uuid.uuid4().hex[:8]}"
        return RunTrace(
            run_id=run_id, scenario_id=self.scenario_id, model=model,
            started_at=time.time(), config=config,
        )

    def write(self, trace: RunTrace) -> None:
        trace.finish()
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict(), default=str) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out