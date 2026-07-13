#!/usr/bin/env python3
"""scrub_and_retire.py — Milestone 1 chain of custody: scrub a landing 'original', then RETIRE it.

For each recording in the secure landing area, run the harness pipeline and — ONLY when redaction
produced a verified compliant (PII-free) recording and did NOT hold — delete the raw PII-bearing audio:
the landing 'original' AND that run's raw `ingest/*.wav` channel splits. The scrubbed `redact/compliant.wav`
(and the PII-free masked channels) are kept. Fail-closed: if redaction HELD or produced no compliant
recording, the original is KEPT and the file is reported as not-retired (never lose audio with no clean copy).

Usage:
  PYTHONPATH=src HF_HUB_OFFLINE=1 ~/.callcenter-harness/venv/bin/python scripts/scrub_and_retire.py [<file>|all]
Config env: LANDING (default ~/.callcenter-harness/landing).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cc_harness.engine.runner import WorkflowRunner  # noqa: E402

LANDING = Path(os.environ.get("LANDING", str(Path.home() / ".callcenter-harness" / "landing")))
RUNS = Path.home() / ".callcenter-harness" / "runs"
AUDIO_EXT = {".mp3", ".wav"}


def _targets(arg: str) -> list[Path]:
    if arg and arg != "all":
        p = Path(arg)
        if not p.is_absolute():
            p = LANDING / arg
        return [p]
    return sorted(f for f in LANDING.glob("*") if f.suffix.lower() in AUDIO_EXT)


def _retire(original: Path, run_id: str) -> list[str]:
    """Delete the raw PII-bearing audio: the landing original + this run's raw ingest channel splits.
    Returns the list of deleted paths. Keeps redact/compliant.wav + masked channels."""
    deleted: list[str] = []
    ingest_dir = RUNS / run_id / "ingest"
    if ingest_dir.is_dir():
        for w in sorted(ingest_dir.glob("*.wav")):  # raw channel splits of the original
            w.unlink()
            deleted.append(str(w))
    if original.exists():
        original.unlink()
        deleted.append(str(original))
    return deleted


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = _targets(arg)
    if not targets:
        print(f"[retire] no audio in landing area {LANDING}")
        return
    retired = kept = 0
    for original in targets:
        if not original.is_file():
            print(f"[retire] SKIP (not found): {original}")
            continue
        run = WorkflowRunner().start("callcenter-qa", {"recording_path": str(original), "profile": "profiles/a1.json"})
        red = run.context.get("redaction") or {}
        compliant = red.get("compliant_recording")
        scrub_ok = (not red.get("held")) and bool(compliant) and Path(compliant).is_file()
        if not scrub_ok:
            reason = red.get("reason") or f"run status={run.status}, no compliant recording"
            print(f"[retire] KEEP  {original.name} — scrub NOT verified ({reason}); original preserved (fail-closed)")
            kept += 1
            continue
        deleted = _retire(original, run.run_id)
        # Verify: original gone, compliant present, no raw ingest wavs remain.
        raw_left = list((RUNS / run.run_id / "ingest").glob("*.wav"))
        assert not original.exists(), f"original still present: {original}"
        assert Path(compliant).is_file(), f"compliant missing: {compliant}"
        assert not raw_left, f"raw ingest splits remain: {raw_left}"
        print(f"[retire] RETIRED {original.name} — scrubbed → {compliant}")
        print(f"          deleted {len(deleted)} raw file(s): "
              + ", ".join(Path(d).name for d in deleted))
        retired += 1
    print(f"\n[retire] DONE: {retired} retired, {kept} kept (fail-closed). "
          f"Landing now holds {len(_targets('all'))} original(s).")


if __name__ == "__main__":
    main()
