#!/usr/bin/env python3
"""Unit tests for Milestone-2 tone scoring (evaluate_prosody pitch/monotone). Run:
PYTHONPATH=src python3 scripts/test_tone_checks.py"""
import sys
from cc_harness.phase_ledger.evaluator import evaluate_prosody as ep

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}");  (c or sys.exit(1))

def line(pitch, energy=60, pace=3.0):
    return f"left turn[0.0-1.0s]: pace={pace}wps pause_before=0.1s pitch={pitch}Hz energy={energy}dB"

# varied pitch → NOT monotone; pitch stats present
r = ep([line(p) for p in (200, 250, 300, 180)], "left")
ck("varied pitch: no monotone flag", "monotone_delivery" not in r["flags"])
ck("mean_pitch + pitch_std reported", r["mean_pitch_hz"] > 0 and r["pitch_std_hz"] > 15 and r["pitch_na"] is False)

# near-constant pitch → monotone
r = ep([line(p) for p in (200, 201, 199, 200)], "left")
ck("monotone pitch: monotone_delivery flagged", "monotone_delivery" in r["flags"] and r["pitch_std_hz"] < 15)

# <2 voiced turns → pitch na, no monotone
r = ep([line(220)], "left")
ck("one voiced turn: pitch_na, no monotone", r["pitch_na"] is True and "monotone_delivery" not in r["flags"])

# unvoiced (pitch=0) excluded from pitch stats
r = ep([line(0), line(0), line(0)], "left")
ck("all-unvoiced: pitch_na true", r["pitch_na"] is True)

# energy/pace flags still work (back-compat) + config threshold honoured
r = ep([line(200, energy=40), line(201, energy=41)], "left", min_energy_db=55, min_pitch_std_hz=1.0)
ck("low energy still flagged", "low_energy_delivery" in r["flags"])
ck("config min_pitch_std_hz=1 → std~0.5<1 monotone", "monotone_delivery" in r["flags"])
r = ep([line(p) for p in (200, 260)], "left", min_pitch_std_hz=1.0)
ck("config threshold: varied not monotone at 1Hz", "monotone_delivery" not in r["flags"])

# masked-duration excluded from pace (Milestone-2 pace confound fix)
from cc_harness.audio.prosody import _masked_overlap
_r = [{"start": 6.0, "end": 7.0}, {"start": 8.0, "end": 9.0}]
ck("pace: full masked overlap", abs(_masked_overlap(6.0, 7.0, _r) - 1.0) < 1e-9)
ck("pace: partial/clipped overlap", abs(_masked_overlap(6.5, 8.0, _r) - 0.5) < 1e-9)
ck("pace: no overlap → 0", _masked_overlap(0.0, 5.0, _r) == 0.0)
ck("pace: multi-span sum", abs(_masked_overlap(5.0, 10.0, _r) - 2.0) < 1e-9)
ck("pace: None ranges → 0", _masked_overlap(0.0, 10.0, None) == 0.0)

print("\nALL TONE UNIT TESTS PASS")
