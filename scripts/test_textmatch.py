#!/usr/bin/env python3
"""STT-robust matching (Fix #1): normalize + exact/near/absent classify, and the (b) behaviour where a
near-match routes a phrase check to review (indeterminate) instead of silently passing or failing.
Run: PYTHONPATH=src python3 scripts/test_textmatch.py"""
import sys
from cc_harness.phase_ledger.textmatch import normalize, classify, best_status
from cc_harness.phase_ledger.primitives import run_primitive


def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))


def ctx(text):
    return {"source_text": text, "customer_text": "", "agent_words": None, "redaction_map": None,
            "mandated_regions": [], "duration": None, "channel": None}


# --- normalize: Latin/Cyrillic homoglyph fold + punctuation/space canonicalisation ---
ck("homoglyph: Latin 'A1' == Cyrillic 'А1'", normalize("A1") == normalize("А1"))
ck("punctuation/space collapsed", normalize("от  името,  на!") == normalize("от името на"))

# --- classify: exact / near / absent ---
ck("classify exact (substring after normalize)", classify("обажда се от името на А1", "А1") == "exact")
ck("classify exact (prefix variant substring)", classify("голяма остъпка днес", "остъпк") == "exact")
ck("classify NEAR (1-edit whole-word STT corruption)", classify("той каза отстапка вече", "отстъпка") == "near")
ck("classify ABSENT (genuinely not present — no false near)", classify("благодаря за времето", "дочуване") == "absent")
ck("classify ABSENT (short word stays exact-only, no fuzzy)", classify("да не", "да1") == "absent")
ck("best_status: any exact wins", best_status("... А1 ...", ["zzz", "А1"]) == "exact")

# --- phrase_present (b): exact->met, near->indeterminate(review), absent->not_met ---
ck("phrase_present exact -> met", run_primitive("phrase_present", {"phrases": ["отстъпк"]},
   ctx("голяма отстъпка"))["status"] == "met")
ck("phrase_present near -> indeterminate (review, not silent met/miss)",
   run_primitive("phrase_present", {"phrases": ["отстъпка"]}, ctx("той каза отстапка"))["status"] == "indeterminate")
ck("phrase_present absent -> not_met (NO false pass)",
   run_primitive("phrase_present", {"phrases": ["дочуване"]}, ctx("приятен ден"))["status"] == "not_met")

# --- forbidden_phrase (b): exact->not_met(violation), near->indeterminate, clean->met ---
ck("forbidden exact -> not_met (violation)", run_primitive("forbidden_phrase", {"phrases": ["дочуване"]},
   ctx("добре, дочуване"))["status"] == "not_met")
ck("forbidden near -> indeterminate (possible violation, review)",
   run_primitive("forbidden_phrase", {"phrases": ["дочуване"]}, ctx("добре, дочуани"))["status"] == "indeterminate")
ck("forbidden clean -> met", run_primitive("forbidden_phrase", {"phrases": ["дочуване"]},
   ctx("благодаря, приятен ден"))["status"] == "met")

print("\nALL TEXTMATCH (Fix #1) TESTS PASS")
