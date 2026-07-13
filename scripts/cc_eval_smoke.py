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

    # Slice 2: deterministic mode now emits a per-criterion CHECKLIST + two-tier severity (the M3 reframe),
    # not a single adherence_score.
    ev = run.context.get("evaluation") or {}
    cl = ev.get("checklist") or []
    check("checklist produced (one row per rubric check)", isinstance(cl, list) and len(cl) > 0)
    check("checklist rows have id/tier/status", all({"id", "tier", "status"} <= set(r) for r in cl))
    check("statuses from the 4-value set", all(r["status"] in ("met", "not_met", "indeterminate", "na") for r in cl))
    check("two-tier severity present", isinstance(ev.get("violations"), list) and isinstance(ev.get("advisories"), list))
    check("indeterminate rollup present", isinstance(ev.get("review_needed"), list))
    check("intonation preserved (M2 tone not dropped)", isinstance(ev.get("intonation"), dict) and "flags" in ev["intonation"])
    check("no single adherence_score headline (reframe)", "manager_summary" not in ev)
    check("evaluate phase output present", bool(run.phases["evaluate-1"].output.strip()))

    ino = ev.get("intonation") or {}
    met = [r["id"] for r in cl if r["status"] == "met"]
    print(f"       contract: {ev.get('contract_key')}")
    print(f"       checklist: {len(met)}/{len(cl)} met | {len(ev.get('violations') or [])} violations "
          f"| {len(ev.get('advisories') or [])} advisories | {len(ev.get('review_needed') or [])} need-review")
    print(f"       violations (hard): {[r['id'] for r in (ev.get('violations') or [])]}")
    print(f"       need-review (CMD/indeterminate): {[r['id'] for r in (ev.get('review_needed') or [])]}")
    print(f"       delivery: pace={ino.get('mean_pace_wps')}wps energy={ino.get('mean_energy_db')}dB flags={ino.get('flags')}")

    print("\nM5 evaluation smoke: ALL PASS")


if __name__ == "__main__":
    main()
