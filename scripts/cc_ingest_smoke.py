#!/usr/bin/env python3
"""M2 smoke: S1 ingest on the real sample + a synthetic non-conversation clip.

    PYTHONPATH=src python3 scripts/cc_ingest_smoke.py [path-to-sample.mp3]

Default sample: ~/Downloads/1783081704.mp3 (real PII call — outputs stay under ~/.callcenter-harness).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
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

    # 1. Real conversation → completed + channel split
    run = WorkflowRunner().start("ingest", {"recording_path": str(sample)})
    ing = run.context.get("ingest", {})
    check("ingest run completed", run.status == "completed", f"status={run.status}")
    check("classified as conversation", ing.get("is_conversation") is True, ing.get("reason", ""))
    split = ing.get("channels_split", {})
    check("stereo split produced left+right", "left" in split and "right" in split, str(list(split)))
    check("left.wav exists", Path(split.get("left", "")).is_file())
    check("right.wav exists", Path(split.get("right", "")).is_file())

    # 2. Synthetic non-conversation (2s silence) → skipped
    with tempfile.TemporaryDirectory() as td:
        silent = Path(td) / "silent.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=stereo",
             "-t", "2", str(silent)],
            capture_output=True, text=True,
        )
        run2 = WorkflowRunner().start("ingest", {"recording_path": str(silent)})
        check("non-conversation run skipped", run2.status == "skipped", f"status={run2.status}")
        check("non-conversation flagged", run2.context.get("ingest", {}).get("is_conversation") is False,
              run2.context.get("ingest", {}).get("reason", ""))

    print("\nM2 ingest smoke: ALL PASS")


if __name__ == "__main__":
    main()
