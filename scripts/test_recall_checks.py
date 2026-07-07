#!/usr/bin/env python3
"""Unit tests for M1 PII recall hardening (H1 Bulgarian number-word runs, H2 email).
Run: PYTHONPATH=src python3 scripts/test_recall_checks.py"""
import sys
from cc_harness.audio import redact as R

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

# H1 number-word runs
sp = R.find_number_word_spans("нула осемдесет и осем седем шест")   # 5 number-words + connector
ck("H1 masks a 5-word phone run", len(sp) == 1 and sp[0].category == "PHONE_OR_ID")
s = sp[0]; ck("H1 span offsets land in text", 0 <= s.start < s.end <= len("нула осемдесет и осем седем шест"))
ck("H1 ignores single number word ('искам две неща')", R.find_number_word_spans("искам две неща") == [])
ck("H1 below threshold: 3 words not masked", R.find_number_word_spans("три четири пет") == [])
ck("H1 at threshold: 4 words masked", len(R.find_number_word_spans("три четири пет шест")) == 1)
ck("H1 trims trailing 'и'", R.find_number_word_spans("две три четири пет и")[0].end == len("две три четири пет"))

# H2 email
sp = R.find_email_spans("пишете на ivan.petrov@abv.bg днес")
ck("H2 masks an email", len(sp) == 1 and sp[0].category == "EMAIL")
ck("H2 email span is the address", "ivan.petrov@abv.bg" == "пишете на ivan.petrov@abv.bg днес"[sp[0].start:sp[0].end])
ck("H2 no email → no span", R.find_email_spans("no at sign here") == [])

# integration: detect_spans (agent channel, include_context=False) catches both, not the script word
spans = R.detect_spans("оферта нула осем осем девет седем шест и мейлът е a@b.bg", ner_hook=None, include_context=False)
cats = {s.category for s in spans}
ck("integration: PHONE_OR_ID + EMAIL detected", "PHONE_OR_ID" in cats and "EMAIL" in cats)
txt = "оферта нула осем осем девет седем шест и мейлът е a@b.bg"
ck("integration: 'оферта' NOT inside any masked span", not any(s.start <= txt.find("оферта") < s.end for s in spans))

print("\nALL RECALL UNIT TESTS PASS")
