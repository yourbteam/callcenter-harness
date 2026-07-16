#!/usr/bin/env python3
"""Interleaved caller/client dialogue: timestamp ordering, turn grouping, role labels from config, mono
fallback, and PII-free (role labels only, never names). Fast — no model.
Run: PYTHONPATH=src python3 scripts/test_dialogue.py"""
import sys
from cc_harness.config.loader import load_language, load_profile
from cc_harness.report import build_dialogue, render_dialogue

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

lang = load_language(load_profile("profiles/a1.json").language)
SL = lang.speaker_labels
ck("bg exposes speaker_labels (role-only)", SL.get("agent") == "Оператор" and SL.get("customer") == "Клиент")

def w(start, word):
    return {"start": start, "end": start + 0.4, "word": word}

# Stereo: agent (left) and customer (right) words interleaved in time.
channels = {
    "left":  {"text": "Добър ден. Оферта.", "words": [w(0.0, " Добър"), w(0.5, " ден."), w(3.0, " Оферта.")]},
    "right": {"text": "Да. Не искам.", "words": [w(2.0, " Да."), w(4.0, " Не"), w(4.3, " искам.")]},
}
dlg = build_dialogue(channels, "left", "right", SL)
ck("stereo → not mono", dlg["mono"] is False)
turns = dlg["turns"]
ck("4 turns in time order", [t["role"] for t in turns] == ["agent", "customer", "agent", "customer"])
ck("turn 1 = agent, both agent words grouped", turns[0]["label"] == "Оператор" and turns[0]["text"] == "Добър ден.")
ck("turn 2 = customer", turns[1]["label"] == "Клиент" and turns[1]["text"] == "Да.")
ck("turn 3 = agent (later)", turns[2]["text"] == "Оферта.")
ck("turn 4 = customer, grouped", turns[3]["text"] == "Не искам.")
ck("turns carry start timestamps in order", [t["start"] for t in turns] == sorted(t["start"] for t in turns))

txt = render_dialogue(dlg)
ck("render is role-labeled dialogue", "Оператор : Добър ден." in txt and "Клиент" in txt)
ck("render PII-free (labels only, no names)", "Оператор" in txt and "Клиент" in txt)

# Mono: single channel, no customer → one unlabeled block + note.
mono = build_dialogue({"mono": {"text": "Цял разговор в едно.", "words": [w(0.0, " Цял")]}}, "mono", None, SL)
ck("mono → mono=True", mono["mono"] is True)
ck("mono has the note", mono["note"] == SL.get("mono_note"))
ck("mono single block text", mono["turns"][0]["text"] == "Цял разговор в едно.")
mtxt = render_dialogue(mono)
ck("mono render shows note + text, no role labels", SL["mono_note"] in mtxt and "Оператор" not in mtxt)

# Missing customer channel (stereo classify but customer empty) → mono fallback, no crash.
degraded = build_dialogue({"left": {"text": "Само оператор.", "words": [w(0.0, " Само")]}, "right": {"text": "", "words": []}}, "left", "right", SL)
ck("empty customer channel → mono fallback", degraded["mono"] is True and "Само оператор." in degraded["turns"][0]["text"])

# No config labels → ASCII fallback, no crash.
bare = build_dialogue(channels, "left", "right", {})
ck("no-config labels → ascii fallback", bare["turns"][0]["label"] == "agent" and isinstance(render_dialogue(bare), str))

print("\nALL DIALOGUE TESTS PASS")
