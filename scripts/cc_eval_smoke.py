#!/usr/bin/env python3
"""M5 smoke: full callcenter-qa pipeline air-gapped, ending in a script-adherence evaluation. Run:

    HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
      PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_eval_smoke.py

Proves: the pipeline classifies the agent channel, selects the per-branch contract via the context
override (§0.7), and produces a script-adherence score with per-element status — no PII printed.
"""
from __future__ import annotations

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
    sample = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "1783081704.mp3"
    check("sample exists", sample.is_file(), str(sample))

    run = WorkflowRunner().start("callcenter-qa", {"recording_path": str(sample), "profile": "profiles/a1.json"})
    for stage in ("redaction", "transcription", "prosody"):
        if (run.context.get(stage) or {}).get("held"):
            check(f"{stage} not held", False, run.context[stage].get("reason", ""))
    check("run completed", run.status == "completed", f"status={run.status}")

    cls = run.context.get("classify") or {}
    check("agent channel identified", bool(cls.get("agent_channel")), f"agent={cls.get('agent_channel')}")
    # classify hands the resolved contract DICT (not a path) to phase_ledger via context (Slice 1).
    ec = run.context.get("evaluation_contract") or {}
    check("contract dict handed to eval via override", bool(ec.get("contract_key")) and "categories_detail" in ec)

    ev = run.context.get("evaluation") or {}
    summ = ev.get("manager_summary") or {}
    check("evaluation produced", "adherence_score" in summ, str(list(summ)))
    check("adherence scored over mandatory only", "mandatory_count" in summ and "matched_mandatory" in summ)
    check("exact source-quote coverage true", summ.get("exact_source_quote_coverage") is True)
    check("intonation evaluated (prosody used)", isinstance(ev.get("intonation"), dict) and "flags" in ev["intonation"])
    check("evaluate phase output present", bool(run.phases["evaluate-1"].output.strip()))

    status = summ.get("category_status") or {}
    present = [c for c, m in status.items() if m]
    missing = [c for c, m in status.items() if not m]
    ino = ev.get("intonation") or {}
    print(f"       contract: {ev.get('contract_key')}")
    print(f"       adherence (mandatory): {summ.get('adherence_score')} "
          f"({summ.get('matched_mandatory')}/{summ.get('mandatory_count')}); optional present "
          f"{summ.get('optional_present')}/{summ.get('optional_count')}")
    print(f"       present: {present}")
    print(f"       missing: {missing}")
    print(f"       findings (missing mandatory): {summ.get('finding_count')}")
    print(f"       delivery: pace={ino.get('mean_pace_wps')}wps energy={ino.get('mean_energy_db')}dB flags={ino.get('flags')}")

    print("\nM5 evaluation smoke: ALL PASS")


if __name__ == "__main__":
    main()
