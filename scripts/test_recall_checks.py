#!/usr/bin/env python3
"""Unit tests for M1 PII recall hardening: H1 number-TOKEN runs (word/digit/mixed), H2 email,
and customer/agent-channel coverage. Run: PYTHONPATH=src python3 scripts/test_recall_checks.py"""
import sys
from cc_harness.audio import redact as R

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

# H1 — number-token runs (word / mixed / digit)
sp = R.find_number_token_spans("нула осемдесет и осем седем шест")     # pure words (regression)
ck("H1 pure-word run masked", len(sp) == 1 and sp[0].category == "PHONE_OR_ID")
sp = R.find_number_token_spans("0 осемдесет осем 9 седем")             # MIXED digit+word (the seam)
ck("H1 MIXED word+digit run masked", len(sp) == 1 and sp[0].category == "PHONE_OR_ID")
ck("H1 ignores single number ('искам две неща')", R.find_number_token_spans("искам две неща") == [])
ck("H1 below threshold: 3 tokens not masked", R.find_number_token_spans("три четири пет") == [])
ck("H1 at threshold: 4 mixed tokens masked", len(R.find_number_token_spans("три 4 пет шест")) == 1)
ck("H1 trims trailing 'и'", R.find_number_token_spans("две три четири пет и")[0].end == len("две три четири пет"))
ck("H1 lone digit not masked", R.find_number_token_spans("канал 5 включен") == [])

# H2 — email
ck("H2 masks an email", len(R.find_email_spans("пишете на ivan.petrov@abv.bg днес")) == 1)
ck("H2 no email → no span", R.find_email_spans("no at sign here") == [])

# T2 — customer & agent path both mask phone(mixed)+email (patterns run on both channels)
txt = "телефонът ми е 0 осем осем 9 седем, мейл a@b.bg"
for ctx, label in ((True, "customer"), (False, "agent")):
    cats = {s.category for s in R.detect_spans(txt, ner_hook=None, include_context=ctx)}
    ck(f"T2 {label} channel masks PHONE_OR_ID + EMAIL", {"PHONE_OR_ID", "EMAIL"} <= cats)

# agent script not over-masked (no 4-token number run in typical price phrasing)
ck("agent price phrase not masked", R.find_number_token_spans("1 евро и 2 цента месечно") == [])

print("\nALL RECALL UNIT TESTS PASS")
