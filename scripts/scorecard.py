#!/usr/bin/env python3
"""Produce a full QA scorecard for one recording via command mode, robustly.

Unlike a throwaway script, this ALWAYS reports the outcome and never fails silently:
  - if the run produced an evaluation -> the full per-criterion checklist + transcripts;
  - if the run was SKIPPED (non-conversation gate) -> the skip reason;
  - if a phase FAILED -> run.context["error"] + the failed phase's error;
  - if start() raised -> the traceback;
  - if nothing above -> an explicit "no evaluation produced" line (never a blank file).

The report is STREAMED line-by-line to a file (default: <recording>.scorecard.txt next to the recording,
overridable with a 2nd arg), each line flushed as it is produced, AND echoed to stdout. Because every line
hits disk immediately, an OS/memory SIGKILL (which cannot be caught) leaves an inspectable PARTIAL file
ending at the point of death — never a silent nothing. A run killed during the STT+judge stage leaves the
explicit "RUN IN PROGRESS" marker as its last line, so a mid-run kill is unambiguous.

Run:
  HF_HUB_OFFLINE=1 NO_PROXY=127.0.0.1 CC_HARNESS_AGENT_COMMAND="<judge cmd>" \
    PYTHONPATH=src python scripts/scorecard.py "<recording>" ["<out.txt>"]
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def build_report(rec: str, sink) -> None:
    """Run command mode and STREAM a complete, never-blank scorecard to `sink`.

    `sink` is a callable writing one flushed line to the output file (see main). Every line is on disk the
    instant it is produced, so a SIGKILL leaves a partial file rather than nothing.
    """
    out = sink

    out(f"RECORDING: {Path(rec).name}")
    out("=" * 80)
    if not Path(rec).is_file():
        out(f"ERROR: recording not found at {rec}")
        return

    from cc_harness.engine.runner import WorkflowRunner
    # This marker is the LAST line on disk if the process is killed during the (uncatchable) STT+judge stage
    # -> a mid-run kill is then unambiguous rather than looking like a clean-but-empty result.
    out("RUN IN PROGRESS (STT + judge)... if this is the last line, the process was killed mid-run.")
    try:
        run = WorkflowRunner().start(
            "callcenter-qa",
            {"recording_path": rec, "execution_mode": "command", "profile": "profiles/a1.json"},
        )
    except Exception as exc:  # noqa: BLE001 - report, never swallow
        out(f"RUN RAISED: {type(exc).__name__}: {exc}")
        out(traceback.format_exc())
        return
    out("RUN COMPLETED (no kill) — rendering scorecard below.")

    ctx = run.context
    out(f"status = {run.status}")
    # Why-no-scorecard diagnostics, always shown:
    if ctx.get("error"):
        out(f"phase error (run.context['error']) = {ctx['error']}")
    for pid, ps in (run.phases or {}).items():
        if getattr(ps, "status", None) == "failed" or (getattr(ps, "output", "") or "").startswith("non_conversation"):
            out(f"phase '{pid}': status={getattr(ps, 'status', '?')} output={getattr(ps, 'output', '')!r} "
                f"error={getattr(ps, 'error', None)!r}")
    ingest = ctx.get("ingest") or {}
    if ingest.get("skipped"):
        out(f"SKIPPED by non-conversation gate: reason={ingest.get('reason')!r} "
            f"(duration={ingest.get('duration_seconds')}s, mean_volume_db={ingest.get('mean_volume_db')})")

    ev = ctx.get("evaluation") or {}
    if not ev:
        out("\nNO EVALUATION PRODUCED (see status / skip / error above).")
        return

    if ev.get("held"):
        out(f"HELD: {ev.get('reason')}")

    tx = (ctx.get("transcription") or {}).get("channels") or {}
    cl = ctx.get("classify") or {}
    ag, cu = cl.get("agent_channel"), cl.get("customer_channel")
    checklist = ev.get("checklist") or []
    out(f"\n=== SCORECARD ({sum(1 for r in checklist if r['status']=='met')}/{len(checklist)} met) ===")
    for r in checklist:
        out(f"  [{r['status']:13}] {r['tier']:4} {r['id']:22} {str(r.get('evidence'))[:90]}")
    out(f"\nhard violations ({len(ev.get('violations') or [])}): "
        + ", ".join(r['id'] for r in (ev.get('violations') or [])))
    out(f"review_needed ({len(ev.get('review_needed') or [])}): "
        + ", ".join(r['id'] for r in (ev.get('review_needed') or [])))
    deal = {r['id']: r for r in checklist}.get("deal")
    out(f"deal: {deal.get('evidence') if deal else None}")
    out(f"intonation: {ev.get('intonation')}")

    at = (tx.get(ag, {}) or {}).get("text", "") or ""
    ct = (tx.get(cu, {}) or {}).get("text", "") or ""
    out(f"\n=== AGENT TRANSCRIPT (redacted, {len(at)} chars) ===\n{at}")
    out(f"\n=== CUSTOMER TRANSCRIPT (redacted, {len(ct)} chars) ===\n{ct}")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: scorecard.py <recording> [out.txt]"); raise SystemExit(2)
    rec = sys.argv[1]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(rec).with_suffix(".scorecard.txt")
    # Open the file up front and flush every line, so an uncatchable SIGKILL still leaves what was written.
    # If the output file itself cannot be opened (unwritable dir, etc.) there is nowhere to stream to — fail
    # LOUD and CLEAR on stderr with the exact reason and path, never a bare traceback the caller must decode.
    try:
        fh = out_path.open("w", encoding="utf-8")
    except OSError as exc:
        print(f"scorecard: cannot open output file {out_path}: {exc}", file=sys.stderr)
        raise SystemExit(3)
    with fh:
        def sink(*a: object) -> None:
            print(*a, file=fh)
            fh.flush()
            print(*a)  # echo to stdout too
        try:
            build_report(rec, sink)
        except Exception:  # noqa: BLE001 - even an unexpected failure must leave an inspectable file
            sink("UNEXPECTED SCRIPT FAILURE:")
            sink(traceback.format_exc())
    print(f"\n[scorecard streamed to {out_path}]")


if __name__ == "__main__":
    main()
