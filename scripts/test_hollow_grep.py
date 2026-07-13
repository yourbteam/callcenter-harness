#!/usr/bin/env python3
"""Slice-1 hollowness grep gate: the engine (src/) must hold NO client/locale literal — all such data
lives in profiles/ + languages/. Run: PYTHONPATH=src python3 scripts/test_hollow_grep.py"""
import re, sys
from pathlib import Path

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

SRC = Path("src")
cyr = re.compile(r"[Ѐ-ӿ]")
# Client/locale literals that must NOT appear anywhere in engine code:
banned = ["offer1_discount", "newplan_esign", "contracts/callcenter", "SCRIPT_MARKERS",
          "BG_NUMBER_WORDS", "CONTEXT_LEAD_INS", "GLINER_LABELS"]

cyr_hits, banned_hits = [], []
for f in SRC.rglob("*.py"):
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if cyr.search(line):
            cyr_hits.append(f"{f}:{i}: {line.strip()[:70]}")
        for b in banned:
            if b in line:
                banned_hits.append(f"{f}:{i}: {b}")

for h in cyr_hits: print("  CYRILLIC:", h)
for h in banned_hits: print("  BANNED  :", h)
ck("no Cyrillic literal anywhere in src/", not cyr_hits)
ck("no client/locale identifier literal in src/", not banned_hits)
print("\nALL HOLLOW-GREP GATE CHECKS PASS")
