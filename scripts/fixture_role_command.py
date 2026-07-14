#!/usr/bin/env python3
"""Fixture judge command for command-backed evaluation tests (no LLM).

Reads the judge prompt on stdin, parses the PHASE CONTRACT + SOURCE REQUEST, and returns a deterministic
JSON judgment: each category is 'conveyed' if a contract keyword appears in the transcript, with an exact
substring as evidence (so the harness's quote-exactness check passes). Emotion/active-listening are canned.
Set CC_HARNESS_AGENT_COMMAND="python3 scripts/fixture_role_command.py" to exercise the command path.
"""
from __future__ import annotations

import json
import sys

prompt = sys.stdin.read()


def _between(text: str, start: str, end: str) -> str:
    if start not in text:
        return ""
    tail = text.split(start, 1)[1]
    return tail.split(end, 1)[0] if end in tail else tail


contract_raw = _between(prompt, "PHASE CONTRACT:\n", "\n\nSOURCE REQUEST:").strip()
source = _between(prompt, "SOURCE REQUEST:\n", "\n\nOUTPUT JSON SHAPE:").strip()


def _section(prefix: str) -> str:
    """Grab the first paragraph under a '## <prefix> …' header of the SOURCE REQUEST."""
    for seg in source.split("## "):
        if seg.startswith(prefix):
            body = seg.split("\n", 1)[1] if "\n" in seg else ""
            return body.split("\n\n", 1)[0].strip()
    return ""


# Restructured rubric prompt: CUSTOMER CHANNEL first, then AGENT TRANSCRIPT (scripted recital).
agent_line = _section("AGENT TRANSCRIPT") or source
customer_line = _section("CUSTOMER CHANNEL")

try:
    contract = json.loads(contract_raw) if contract_raw else {}
except json.JSONDecodeError:
    contract = {}

if "checks" in contract:  # NEW rubric-driven judge shape (Slice 3 + evidence-forced restructure)
    quote = agent_line[:40]           # a real substring of the AGENT transcript (passes NFR-5)
    cust_q = customer_line[:40]        # a real substring of the CUSTOMER channel
    checks = {str(c.get("id")): {"met": True, "evidence": quote, "customer_evidence": cust_q,
                                 "detail": "fixture met"}
              for c in contract.get("checks", [])}
    # Evidence-forced deal: accept_quote must be a REAL substring of the customer channel; only when the
    # customer's words contain an acceptance cue does the fixture emit a (verbatim) acceptance quote.
    accept = ""
    cl = customer_line.lower()
    for w in ("приемам", "приемате", "съгласен", "съгласна", "да, разбира"):
        pos = cl.find(w)
        if pos != -1:
            accept = customer_line[pos:pos + 30].strip()
            break
    print(json.dumps({
        "checks": checks,
        "deal": {"happened": bool(accept), "accept_quote": accept,
                 "consent": bool(accept), "refusal": False},
        "path": {"is_titular": True, "decision_maker": True, "service": "fixed"},
        "emotion": {"score": 0.7}, "active_listening": {"score": 0.6},
        "objection": {"raised": False, "rebutted": False, "matched": False, "evidence": ""},
        "notes": "deterministic fixture judgment (no model call)",
    }, ensure_ascii=False))
else:  # legacy categories_detail shape (evaluate_command)
    elements = []
    for detail in contract.get("categories_detail", []):
        evidence, conveyed = "", 0.0
        for kw in detail.get("keywords", []):
            pos = low.find(str(kw).lower())
            if pos != -1:
                evidence = (agent_line or source)[max(0, pos - 30): pos + len(str(kw)) + 30].strip()
                conveyed = 0.9
                break
        elements.append({"category": str(detail.get("category")), "present": conveyed > 0,
                         "conveyed": conveyed, "evidence": evidence})
    print(json.dumps({
        "elements": elements,
        "emotion": {"score": 0.7, "assessment": "fixture: adequate warmth/confidence"},
        "active_listening": {"score": 0.6, "assessment": "fixture: some responsiveness"},
        "notes": "deterministic fixture judgment (no model call)",
    }, ensure_ascii=False))
