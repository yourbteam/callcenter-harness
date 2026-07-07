#!/usr/bin/env python3
"""M3 smoke: air-gapped S1+S2 redaction on the real sample. Run under the venv python:

    ~/.callcenter-harness/venv/bin/python -m pip show faster-whisper >/dev/null   # deps present
    HF_HUB_OFFLINE=1 HTTPS_PROXY=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 \
      PYTHONPATH=src ~/.callcenter-harness/venv/bin/python scripts/cc_redact_smoke.py

Proves: run completes (not held), a compliant recording is produced, the redaction map has entries with
NO PII values (timestamps + category only), and it all runs with the network black-holed (NFR-7).
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

    run = WorkflowRunner().start("redact", {"recording_path": str(sample)})
    red = run.context.get("redaction", {})
    if red.get("held"):
        check("redaction not held", False, f"held: {red.get('reason')}")
    check("run completed", run.status == "completed", f"status={run.status}")
    check("compliant recording produced", bool(red.get("compliant_recording")))
    check("compliant recording exists on disk", Path(red.get("compliant_recording", "")).is_file())

    rmap = red.get("redaction_map", [])
    check("redaction map has entries", len(rmap) > 0, f"{len(rmap)} spans")
    # FR-2.4: map carries NO PII values — only start/end/category/channel.
    allowed = {"start", "end", "category", "channel"}
    check("redaction map has no PII values", all(set(e).issubset(allowed) for e in rmap),
          f"keys={sorted({k for e in rmap for k in e})}")
    cats = sorted({e["category"] for e in rmap})
    print(f"       categories masked: {cats}")
    print(f"       spans masked: {len(rmap)}")

    print("\nM3 redaction smoke: ALL PASS")


if __name__ == "__main__":
    main()
