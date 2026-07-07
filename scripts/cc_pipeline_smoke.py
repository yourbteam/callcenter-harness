#!/usr/bin/env python3
"""M4 smoke: full S1-S3' pipeline air-gapped on the real sample. Run under the venv python:

    HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
      PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_pipeline_smoke.py

Proves: ingest -> redaction -> transcription (off the compliant recording) -> prosody all complete
air-gapped; the eval transcript comes from the masked audio (PII-free); prosody emits a text summary.
"""
from __future__ import annotations

import re
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

    run = WorkflowRunner().start("pipeline", {"recording_path": str(sample)})
    if (run.context.get("redaction") or {}).get("held"):
        check("redaction not held", False, run.context["redaction"].get("reason", ""))
    check("pipeline run completed", run.status == "completed", f"status={run.status}")

    # S3 transcription off the compliant recording
    tr = (run.context.get("transcription") or {}).get("channels") or {}
    check("transcription produced per channel", len(tr) >= 1, f"channels={list(tr)}")
    check("eval transcript has text", any((c.get("text") or "").strip() for c in tr.values()))
    check("transcription phase output present", bool(run.phases["transcribe-1"].output.strip()))

    # S3' prosody
    lines = (run.context.get("prosody") or {}).get("summary_lines") or []
    check("prosody summary produced", len(lines) > 0, f"{len(lines)} turn-lines")
    check("prosody lines carry pitch+pace+energy",
          all(re.search(r"pace=.*pause_before=.*pitch=.*energy=", ln) for ln in lines[:5]),
          f"e.g. {lines[0] if lines else ''}")
    check("prosody phase output present", bool(run.phases["prosody-1"].output.strip()))

    print(f"       transcript channels: {list(tr)}; prosody turn-lines: {len(lines)}")
    print("\nM4 pipeline smoke: ALL PASS")


if __name__ == "__main__":
    main()
