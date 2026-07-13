#!/usr/bin/env python3
"""Slice-1 hollowness proof (T1 new-client + T2 new-locale) — a 2nd client/locale plugs in via JSON with
ZERO code change. Fast (no models). Run: PYTHONPATH=src python3 scripts/test_hollow_demo.py"""
import sys
from cc_harness.config.loader import load_profile, load_language
from cc_harness.audio import redact as R

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

# T1 — a different CLIENT profile loads with its own markers/contract/offer-category
demo = load_profile("profiles/demo-mock.json")
ck("demo profile loads", demo.client_key == "demo" and demo.offer_category_id == "promo")
ck("demo has its own agent markers", demo.agent_markers == ["widget", "warranty", "upgrade"])
# agent-channel picker uses the DEMO markers (not A1's) — same engine fn, different data
texts = {"L": "please upgrade your warranty widget today", "R": "no thanks"}
ck("agent-channel picked via demo markers", R.pick_agent_channel(texts, demo.agent_markers) == "L")

# T2 — a different LOCALE pack changes the recognizer behavior with no code change
xx = load_language("xx")
ck("xx locale loads (egn off, iban XX)", xx.egn is False and xx.iban_prefix == "XX")
# EGN is OFF for xx → a valid-EGN-shaped 10-digit run is NOT classified EGN (it's PHONE_OR_ID)
ck("xx: EGN recognizer disabled", R._classify_number("8001010010", egn=xx.egn) != "EGN")
# A1 (bg) EGN stays ON — same fn, different config
bg = load_language("bg")
# IBAN prefix follows the locale: XX-IBAN matches under xx, BG-IBAN does not
xx_iban = "XX00" + "A" * 18
bg_iban = "BG00" + "A" * 18
ck("xx: matches XX-IBAN", any(s.category == "IBAN" for s in R.find_pattern_spans(xx_iban, xx.iban_prefix, xx.egn)))
ck("xx: does NOT match BG-IBAN", not any(s.category == "IBAN" for s in R.find_pattern_spans(bg_iban, xx.iban_prefix, xx.egn)))
ck("bg: matches BG-IBAN", any(s.category == "IBAN" for s in R.find_pattern_spans(bg_iban, bg.iban_prefix, bg.egn)))

# detect_spans runs end-to-end with the demo/xx config (different number-words/connector/cues) — no code change
spans = R.detect_spans("call me one two three four and five at address Foo",
                       number_words=xx.number_words, connector=xx.number_connector,
                       lead_ins=xx.context_lead_ins, iban_prefix=xx.iban_prefix, egn=xx.egn,
                       ner_hook=None, include_context=True)
ck("demo/xx detect_spans runs + finds the English number run", any(s.category == "PHONE_OR_ID" for s in spans))

print("\nALL HOLLOW-DEMO (T1 client + T2 locale) TESTS PASS")
