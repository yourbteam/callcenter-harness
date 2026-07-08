#!/usr/bin/env python3
"""Unit tests for the NER transcript chunker (_chunks) — long-call truncation fix.
Pure-Python, no models. Run: PYTHONPATH=src python3 scripts/test_ner_chunk.py"""
import sys
from cc_harness.audio.ner import _chunks, NER_MAX_CHARS, NER_OVERLAP_CHARS

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}");  (c or sys.exit(1))

M, OV = NER_MAX_CHARS, NER_OVERLAP_CHARS

# short text -> single (0, text) window == single-pass parity (A4)
ck("short text -> one window (0,text)", _chunks("здравей") == [(0, "здравей")])
ck("exactly max_chars -> one window", _chunks("x" * M) == [(0, "x" * M)])

# long no-whitespace string: terminates, every window <= max_chars, covers whole text (A9, F8)
big = "x" * 5000
cs = _chunks(big)
ck("no-space: >1 window", len(cs) > 1)
ck("no-space: every window <= max_chars", all(len(s) <= M for _, s in cs))
ck("no-space: first window starts at 0", cs[0][0] == 0)
ck("no-space: last window reaches end", cs[-1][0] + len(cs[-1][1]) == len(big))
# reconstruct-coverage: every index of the text is inside some window
covered = [False] * len(big)
for base, s in cs:
    for i in range(base, base + len(s)):
        covered[i] = True
ck("no-space: whole text covered", all(covered))

# windows advance strictly (termination witness) and don't exceed cap
starts = [b for b, _ in cs]
ck("strictly increasing starts", all(b2 > b1 for b1, b2 in zip(starts, starts[1:])))

# whitespace text: words not split (each window ends at a space or the text end)
words = " ".join(["дума%d" % i for i in range(400)])   # ~ >max_chars with spaces
cw = _chunks(words)
ck("spaced: >1 window", len(cw) > 1)
ck("spaced: windows <= max_chars", all(len(s) <= M for _, s in cw))
for base, s in cw[:-1]:
    # a non-final window either ended on a space boundary in the source, or hard-capped
    nxt = words[base + len(s): base + len(s) + 1]
    ck("spaced: non-final window ends at boundary", s.endswith(" ") is False and (nxt == " " or nxt == ""))

# boundary entity: a name placed to straddle a window edge appears WHOLE in some window (overlap, A5)
name = "Радослава Кавалджиева"
# place the name so it starts just before the first hard boundary (~max_chars - 5)
pos = M - 5
doc = ("а " * ((pos) // 2))[:pos] + name + (" б" * 200)
cb = _chunks(doc)
whole = any(name in s for _, s in cb)
ck("boundary name contained whole in a window (overlap)", whole)
# and its absolute offset via that window maps back to the real position
abs_ok = any(base + s.find(name) == doc.find(name) for base, s in cb if name in s)
ck("boundary name absolute offset via base is exact", abs_ok)

# overlap sanity: consecutive windows overlap by ~overlap (recovers boundary entities)
if len(cs) > 1:
    b0, s0 = cs[0]
    b1, _ = cs[1]
    ck("no-space: step ~ max_chars - overlap", b1 == (b0 + len(s0)) - OV or b1 == b0 + 1)

# pathological: a stale space near the start must NOT explode into O(n) tiny windows.
# "word " + long unbroken run -> window count stays ~ 2n/max_chars, not O(n).
patho = "дума " + ("щ" * 4000)
cp = _chunks(patho)
ck("patho: windows <= max_chars", all(len(s) <= M for _, s in cp))
ck("patho: whole text covered", sum(len(s) for _, s in cp) >= len(patho))  # >= due to overlap
ck("patho: bounded window count (not O(n))", len(cp) <= (2 * len(patho)) // M + 3)
# every window still at least half-full except possibly the last (progress guarantee)
ck("patho: non-final windows >= max_chars//2", all(len(s) >= M // 2 for _, s in cp[:-1]))

print("\nALL NER CHUNKER UNIT TESTS PASS")
