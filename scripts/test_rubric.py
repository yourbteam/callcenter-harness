#!/usr/bin/env python3
"""Unit tests for the Slice-2 rubric-interpreter + loader rubric validation. Fast (no models).
Run: PYTHONPATH=src python3 scripts/test_rubric.py"""
import json, sys, tempfile
from pathlib import Path
from cc_harness.phase_ledger.rubric import run_rubric
from cc_harness.config.loader import load_profile, ConfigError

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

def ctx(text):
    return {"source_text": text, "agent_words": None, "redaction_map": [], "mandated_regions": [],
            "duration": None, "channel": None}

rubric = [
    {"id": "a", "primitive": "phrase_present", "tier": "hard", "phrases": ["hello"]},   # met
    {"id": "b", "primitive": "phrase_present", "tier": "hard", "phrases": ["missing"]}, # not_met → violation
    {"id": "c", "primitive": "word_avoid", "tier": "soft", "words": ["bad"]},           # soft advisory
    {"id": "d", "primitive": "conditional_on", "tier": "hard", "condition": "deal",     # indeterminate → review
     "check": {"primitive": "phrase_present", "phrases": ["x"]}},
]
out = run_rubric(rubric, ctx("hello there, nothing bad"))
ck("checklist has a row per check", len(out["checklist"]) == 4)
ck("met/not_met/indeterminate statuses assigned",
   {r["id"]: r["status"] for r in out["checklist"]} == {"a": "met", "b": "not_met", "c": "not_met", "d": "indeterminate"})
ck("violations = hard & not_met only", [r["id"] for r in out["violations"]] == ["b"])
ck("advisories = soft rows", [r["id"] for r in out["advisories"]] == ["c"])
ck("review_needed = indeterminate rows", [r["id"] for r in out["review_needed"]] == ["d"])

# applies_to_paths carried through
out2 = run_rubric([{"id": "p", "primitive": "phrase_present", "tier": "hard", "phrases": ["hi"], "applies_to_paths": ["titular"]}], ctx("hi"))
ck("applies_to_paths preserved on the checklist row", out2["checklist"][0]["applies_to_paths"] == ["titular"])

# loader fail-closed on a malformed rubric entry (M3 §11)
tmp = Path(tempfile.mkdtemp())
def bad_profile(rubric_val):
    p = {"schema_version": 1, "client_key": "x", "language": "bg", "agent_markers": ["a"],
         "offer_category_id": "o", "contract": {"contract_key": "k", "id_prefix": "K", "categories_detail": []},
         "rubric": rubric_val}
    f = tmp / "p.json"; f.write_text(json.dumps(p), encoding="utf-8"); return str(f)
def raises(fn):
    try:
        fn(); return False
    except ConfigError:
        return True
ck("rubric entry missing id → ConfigError", raises(lambda: load_profile(bad_profile([{"primitive": "phrase_present", "tier": "hard"}]))))
ck("rubric entry missing primitive → ConfigError", raises(lambda: load_profile(bad_profile([{"id": "a", "tier": "hard"}]))))
ck("rubric entry bad tier → ConfigError", raises(lambda: load_profile(bad_profile([{"id": "a", "primitive": "phrase_present", "tier": "maybe"}]))))
ck("valid rubric loads", load_profile(bad_profile([{"id": "a", "primitive": "phrase_present", "tier": "hard"}])).rubric[0]["id"] == "a")

print("\nALL RUBRIC-INTERPRETER TESTS PASS")
