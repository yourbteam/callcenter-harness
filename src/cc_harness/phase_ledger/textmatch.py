"""STT-robust phrase matching (generic; no client/locale vocab here — phrases live in the profile).

8kHz-telephony STT corrupts the transcript: mixed Latin/Cyrillic homoglyphs, punctuation/spacing noise, and
occasional dropped/altered letters. Exact substring matching then FALSE-fails real script phrases. This module
canonicalises both sides (safe, no false-pass risk) and classifies a phrase as:

    "exact"  — the normalised phrase is a substring of the normalised transcript  → treat as a hit
    "near"   — not exact, but every phrase word fuzzy-matches a consecutive transcript word (bounded, length
               -scaled edit distance)                                             → REVIEW (human confirm)
    "absent" — neither                                                            → treat as a miss

A `near` result never silently passes or fails a check; it routes the criterion to review_needed. So an
imperfect fuzzy match can only ever add a review flag — it can never hide a real compliance gap.
"""
from __future__ import annotations

import re
import unicodedata

# Fold the 7 Latin letters that are true lowercase look-alikes of Cyrillic ones onto their Cyrillic
# code points, so a mixed-script "A1" and a native brand token canonicalise identically. Built from code
# points (not literals) so the engine source stays ASCII per the hollow-grep gate. Only genuine homoglyphs
# are folded -- over-folding would merge distinct letters and manufacture false matches. Applied after
# casefold. Latin keys a e o p c y x  ->  U+0430 U+0435 U+043E U+0440 U+0441 U+0443 U+0445.
_HOMOGLYPH = str.maketrans(dict(zip("aeopcyx", map(chr, (0x430, 0x435, 0x43E, 0x440, 0x441, 0x443, 0x445)))))
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(s: str) -> str:
    """Canonicalise for matching: NFKC, casefold, Latin→Cyrillic homoglyph fold, strip punctuation, collapse
    whitespace. Deterministic and meaning-preserving — it only unifies confusable glyphs and spacing, so it
    can never turn an absent phrase into a present one."""
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = s.translate(_HOMOGLYPH)
    s = _PUNCT.sub(" ", s)
    return _WS.sub(" ", s).strip()


def _thresh(n: int) -> int:
    """Length-scaled edit-distance budget for a single word — tight so `near` stays rare."""
    return 0 if n <= 4 else (1 if n <= 7 else 2)


def _lev_le(a: str, b: str, k: int) -> bool:
    """True iff Levenshtein(a, b) <= k. Bounded DP with per-row early exit."""
    if k <= 0:
        return a == b
    if abs(len(a) - len(b)) > k:
        return False
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        row_best = cur[0]
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            row_best = min(row_best, cur[j])
        if row_best > k:
            return False
        prev = cur
    return prev[-1] <= k


def classify(text: str, phrase: str) -> str:
    """Return "exact" | "near" | "absent" for `phrase` against `text` (both normalised internally)."""
    nt, npz = normalize(text), normalize(phrase)
    if not npz:
        return "absent"
    if npz in nt:
        return "exact"
    ttoks, ptoks = nt.split(), npz.split()
    if not ttoks or len(ptoks) > len(ttoks):
        return "absent"
    # near: a consecutive run of transcript words that each fuzzy-match the phrase words in order.
    for s in range(len(ttoks) - len(ptoks) + 1):
        if all(_lev_le(ptoks[k], ttoks[s + k], _thresh(len(ptoks[k]))) for k in range(len(ptoks))):
            return "near"
    return "absent"


def best_status(text: str, phrases: list[str]) -> str:
    """Across several candidate phrases, the strongest evidence wins: any exact → exact; else any near →
    near; else absent."""
    seen_near = False
    for p in phrases:
        st = classify(text, str(p))
        if st == "exact":
            return "exact"
        if st == "near":
            seen_near = True
    return "near" if seen_near else "absent"
