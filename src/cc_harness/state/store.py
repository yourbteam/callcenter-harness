"""Durable local workflow state store.

Forked from `up_harness/state/store.py` (see requirements-foundation §9). `PhaseState.output` stays a
`str` (a JSON summary + any artifact path); binary audio artifacts are referenced by path in
`WorkflowRun.context`, never inlined (plan §0.3).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


STATE_DIR = Path(".cc-harness-state")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PhaseState:
    phase_id: str
    status: str = "pending"
    output: str = ""
    error: str | None = None


@dataclass
class WorkflowRun:
    run_id: str
    workflow_name: str
    status: str = "running"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    context: dict[str, Any] = field(default_factory=dict)
    phases: dict[str, PhaseState] = field(default_factory=dict)

    @classmethod
    def create(cls, workflow_name: str, context: dict[str, Any] | None = None) -> "WorkflowRun":
        return cls(
            run_id=f"cc-run-{uuid4().hex[:12]}",
            workflow_name=workflow_name,
            context=context or {},
        )


class WorkflowStateStore:
    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_id: str) -> Path:
        return self.state_dir / f"{run_id}.json"

    def save(self, run: WorkflowRun) -> None:
        run.updated_at = _now()
        path = self.path_for(run.run_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")
        tmp.replace(path)

    def load(self, run_id: str) -> WorkflowRun:
        data = json.loads(self.path_for(run_id).read_text(encoding="utf-8"))
        phases = {pid: PhaseState(**pstate) for pid, pstate in (data.pop("phases", {}) or {}).items()}
        return WorkflowRun(phases=phases, **data)
