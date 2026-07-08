"""Workflow definitions + loader.

Forked/minimized from `up_harness/engine/workflow.py`. Workflows are JSON documents under `workflows/`
(a phase list). M1 supports the `noop` phase type; audio/eval phase types arrive in later milestones.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WORKFLOWS_DIR = Path("workflows")


@dataclass(frozen=True)
class WorkflowPhase:
    id: str
    name: str
    type: str
    depends_on: list[str] = field(default_factory=list)
    subscribes_to: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    description: str
    version: str
    phases: list[WorkflowPhase]

    def execution_order(self) -> list[WorkflowPhase]:
        """Phases in dependency order (stable: phases with satisfied deps run in original list order).
        Makes the declared `depends_on` graph load-bearing so a workflow can't be silently mis-ordered
        by editing the JSON list order. Fail-closed: a duplicate id, an unknown `depends_on`, or a
        dependency cycle raises ValueError. Already-topological workflows are returned unchanged."""
        by_id: dict[str, WorkflowPhase] = {}
        for p in self.phases:
            if p.id in by_id:
                raise ValueError(f"duplicate phase id: {p.id!r}")
            by_id[p.id] = p
        for p in self.phases:
            for dep in p.depends_on:
                if dep not in by_id:
                    raise ValueError(f"phase {p.id!r} depends_on unknown phase {dep!r}")
        order: list[WorkflowPhase] = []
        done: set[str] = set()
        remaining = [p.id for p in self.phases]  # preserve original list order
        while remaining:
            ready = [pid for pid in remaining if all(d in done for d in by_id[pid].depends_on)]
            if not ready:
                raise ValueError(f"dependency cycle among phases: {remaining}")
            for pid in ready:  # list-order stable among independents
                order.append(by_id[pid])
                done.add(pid)
                remaining.remove(pid)
        return order


def _phase_from_dict(raw: dict[str, Any]) -> WorkflowPhase:
    known = {"id", "name", "type", "depends_on", "subscribes_to"}
    config = {k: v for k, v in raw.items() if k not in known}
    return WorkflowPhase(
        id=str(raw["id"]),
        name=str(raw.get("name") or raw["id"]),
        type=str(raw["type"]),
        depends_on=list(raw.get("depends_on") or []),
        subscribes_to=list(raw.get("subscribes_to") or []),
        config=config,
    )


def load_workflow(name: str, workflows_dir: Path = WORKFLOWS_DIR) -> WorkflowDefinition:
    path = workflows_dir / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"Unknown workflow: {name} (looked for {path})")
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowDefinition(
        name=str(data["name"]),
        description=str(data.get("description") or ""),
        version=str(data.get("version") or "0.0.0"),
        phases=[_phase_from_dict(p) for p in data.get("phases", [])],
    )


def list_workflows(workflows_dir: Path = WORKFLOWS_DIR) -> list[str]:
    if not workflows_dir.is_dir():
        return []
    return sorted(p.stem for p in workflows_dir.glob("*.json"))
