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

try:
    contract = json.loads(contract_raw) if contract_raw else {}
except json.JSONDecodeError:
    contract = {}

low = source.lower()
elements = []
for detail in contract.get("categories_detail", []):
    category = str(detail.get("category"))
    evidence = ""
    conveyed = 0.0
    for kw in detail.get("keywords", []):
        pos = low.find(str(kw).lower())
        if pos != -1:
            evidence = source[max(0, pos - 30): pos + len(str(kw)) + 30].strip()
            conveyed = 0.9
            break
    elements.append({
        "category": category,
        "present": conveyed > 0,
        "conveyed": conveyed,
        "evidence": evidence,
    })

print(json.dumps({
    "elements": elements,
    "emotion": {"score": 0.7, "assessment": "fixture: adequate warmth/confidence"},
    "active_listening": {"score": 0.6, "assessment": "fixture: some responsiveness"},
    "notes": "deterministic fixture judgment (no model call)",
}, ensure_ascii=False))
