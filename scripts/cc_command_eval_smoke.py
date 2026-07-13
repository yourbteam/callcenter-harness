#!/usr/bin/env python3
"""Command-backed evaluation smoke: model-judged eval via the fixture judge, + fail-closed. Run:

    HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 \
      CC_HARNESS_AGENT_COMMAND="python3 $PWD/scripts/fixture_role_command.py" \
      PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_command_eval_smoke.py <REC>

Proves: execution_mode=command routes to the model judge (adherence + emotion + active-listening, with
exact-quote coverage), and that command mode HOLDs fail-closed when CC_HARNESS_AGENT_COMMAND is unset.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from cc_harness.engine.runner import WorkflowRunner  # noqa: E402


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        raise SystemExit(1)


def main() -> None:
    rec = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Downloads" / "1783081704.mp3")
    check("sample exists", Path(rec).is_file(), rec)
    _cmd = os.environ.get("CC_HARNESS_AGENT_COMMAND", "")
    check(f"CC_HARNESS_AGENT_COMMAND set → {_cmd or '(unset)'}", bool(_cmd))

    run = WorkflowRunner().start("callcenter-qa", {"recording_path": rec, "execution_mode": "command", "profile": "profiles/a1.json"})
    ev = run.context.get("evaluation", {})
    check("command-mode run completed", run.status == "completed" and not ev.get("held"), f"status={run.status}")
    check("mode is command", ev.get("mode") == "command")
    # Slice 3: command mode emits the same CHECKLIST shape as deterministic, but the CMD rows (deal/path/
    # judge_check) are now RESOLVED via the judge instead of indeterminate.
    cl = ev.get("checklist") or []
    check("checklist produced", isinstance(cl, list) and len(cl) > 0)
    check("two-tier + review rollups present",
          all(isinstance(ev.get(k), list) for k in ("violations", "advisories", "review_needed")))
    check("intonation preserved", isinstance(ev.get("intonation"), dict) and "flags" in ev["intonation"])
    ids = {r["id"]: r for r in cl}
    cmd_ids = [i for i in ("deal", "path", "objection_effort", "active_listening", "emotion") if i in ids]
    check("CMD checks present in the checklist", len(cmd_ids) >= 3, str(cmd_ids))
    check("CMD checks RESOLVED by the judge (not all indeterminate)",
          any(ids[i]["status"] in ("met", "not_met", "na") for i in cmd_ids), str({i: ids[i]["status"] for i in cmd_ids}))
    met = sum(1 for r in cl if r["status"] == "met")
    print(f"       checklist: {met}/{len(cl)} met | {len(ev.get('violations') or [])} viol "
          f"| {len(ev.get('review_needed') or [])} review | CMD: {{{', '.join(f'{i}={ids[i]['status']}' for i in cmd_ids)}}}")

    # Fail-closed: same run without the command configured must HOLD.
    saved = os.environ.pop("CC_HARNESS_AGENT_COMMAND", None)
    try:
        run2 = WorkflowRunner().start("callcenter-qa", {"recording_path": rec, "execution_mode": "command", "profile": "profiles/a1.json"})
    finally:
        if saved is not None:
            os.environ["CC_HARNESS_AGENT_COMMAND"] = saved
    ev2 = run2.context.get("evaluation", {})
    check("fail-closed HOLD when command unconfigured", run2.status == "blocked" and ev2.get("held") is True,
          ev2.get("reason", ""))

    print("\nCommand-eval smoke: ALL PASS")


if __name__ == "__main__":
    main()
