#!/usr/bin/env python3
"""Unit tests for the two engine upgrades: depends_on topological ordering + per-phase retry.
Pure (no audio/models). Run from repo root: PYTHONPATH=src python3 scripts/test_engine_upgrades.py"""
import sys, tempfile
from pathlib import Path
from cc_harness.engine.workflow import WorkflowDefinition, WorkflowPhase, load_workflow, list_workflows
from cc_harness.engine.runner import WorkflowRunner
from cc_harness.state.store import WorkflowStateStore

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}");  (c or sys.exit(1))

def P(pid, deps=()):
    return WorkflowPhase(id=pid, name=pid, type="noop", depends_on=list(deps), subscribes_to=[], config={})
def WF(phases):
    return WorkflowDefinition(name="t", description="", version="0", phases=phases)
def ids(phases):
    return [p.id for p in phases]

# ---- Topological ordering ----
# T1: all shipped workflows are already topological → execution_order reproduces list order (no behavior change)
for name in list_workflows():
    wf = load_workflow(name)
    ck(f"T1 {name}: execution_order == list order", ids(wf.execution_order()) == ids(wf.phases))

# T2: list order violating deps is corrected so each phase follows its deps
ck("T2 reorders to honor deps", ids(WF([P("c", ["b"]), P("b", ["a"]), P("a")]).execution_order()) == ["a", "b", "c"])
# T6: independents keep original list order (stable)
ck("T6 stable independents", ids(WF([P("a"), P("b"), P("c")]).execution_order()) == ["a", "b", "c"])
ck("T6 diamond honors deps + stable", ids(WF([P("a"), P("b", ["a"]), P("c", ["a"]), P("d", ["b", "c"])]).execution_order()) == ["a", "b", "c", "d"])

def raises(fn):
    try:
        fn(); return False
    except ValueError:
        return True
# T3 unknown dep, T4 cycle, T5 duplicate id
ck("T3 unknown depends_on raises", raises(lambda: WF([P("a", ["ghost"])]).execution_order()))
ck("T4 cycle raises", raises(lambda: WF([P("a", ["b"]), P("b", ["a"])]).execution_order()))
ck("T5 duplicate id raises", raises(lambda: WF([P("a"), P("a")]).execution_order()))

# ---- Per-phase retry ----
class FailNTimes:
    def __init__(self, n): self.n, self.calls = n, 0
    def __call__(self, run, phase, phase_state):
        self.calls += 1
        if self.calls <= self.n:
            raise RuntimeError(f"transient failure {self.calls}")
        phase_state.output = "ok"

def new_runner(**kw):
    store = WorkflowStateStore(Path(tempfile.mkdtemp()) / "state")
    return WorkflowRunner(store, **kw), store

def only_phase(run):
    (pid,) = tuple(run.phases)  # noop workflow has exactly one phase
    return run.phases[pid]

# R1: fail once then succeed (max_attempts=2) → completed, attempts==2, error cleared
r, store = new_runner(default_max_attempts=2)
r._run_noop_phase = FailNTimes(1)
run = r.start("noop", {})
ps = only_phase(run)
ck("R1 completes after one retry", run.status == "completed" and ps.status == "completed")
ck("R1 attempts == 2", ps.attempts == 2)
ck("R1 error cleared on success", ps.error is None)
# R5: attempts persisted (round-trip)
ck("R5 attempts persisted", store.load(run.run_id).phases[ps.phase_id].attempts == 2)

# R2: always fails (max_attempts=3) → failed, attempts==3 (start() catches the raise)
r, _ = new_runner(default_max_attempts=3)
r._run_noop_phase = FailNTimes(99)
run = r.start("noop", {})
ps = only_phase(run)
ck("R2 run failed after exhausting attempts", run.status == "failed" and ps.status == "failed")
ck("R2 attempts == 3", ps.attempts == 3)
ck("R2 error recorded", (ps.error or "").startswith("transient failure"))

# R3: default max_attempts=1 → no retry (behavior preserved)
r, _ = new_runner()  # default_max_attempts=1
r._run_noop_phase = FailNTimes(99)
run = r.start("noop", {})
ck("R3 no retry by default → attempts == 1", only_phase(run).attempts == 1 and run.status == "failed")

# R4: a HOLD/skip (sets run.status without raising) is NOT retried
def hold_handler(run, phase, phase_state):
    run.status = "blocked"
    phase_state.output = "held"
r, _ = new_runner(default_max_attempts=3)
r._run_noop_phase = hold_handler
run = r.start("noop", {})
ps = only_phase(run)
ck("R4 HOLD not retried → attempts == 1", ps.attempts == 1)
ck("R4 HOLD is terminal blocked", run.status == "blocked" and ps.status == "blocked")

print("\nALL ENGINE-UPGRADE UNIT TESTS PASS")
