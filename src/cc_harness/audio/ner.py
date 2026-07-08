"""Offline NER hook for redaction — Bulgarian transformers NER + GLiNER (names/addresses).

Fail-closed (NFR-6/FR-2.3): if a model is not vendored/loadable, loading RAISES. The redaction phase
catches that and HOLDS the call rather than silently under-detecting. All offline (NFR-7): weights are
vendored and `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` are forced on.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from cc_harness.audio.redact import Span  # noqa: E402

MODELS = Path(os.path.expanduser("~/.callcenter-harness/models"))
BG_NER_DIR = MODELS / "bg-ner"
GLINER_DIR = MODELS / "gliner-multi"

# GLiNER zero-shot labels (Bulgarian) for the entities we redact.
GLINER_LABELS = ["име", "фамилия", "адрес", "населено място", "организация"]

# Long-call recall: both NER models truncate a single forward pass (bg-ner ~512 tok, GLiNER 384 tok —
# confirmed empirically: a name spoken late in a long transcript is dropped), so window the transcript
# and run both models per window. 600 chars ≈ 300-400 Cyrillic sub-word tokens (under GLiNER's 384);
# 150-char overlap ≥ any realistic name+address entity, so a boundary-straddling entity is fully
# contained in at least one window. Offsets are translated back to absolute positions in `ner_spans`.
NER_MAX_CHARS = 600
NER_OVERLAP_CHARS = 150


def models_present() -> bool:
    # GLiNER stores its config as `gliner_config.json` (not `config.json`).
    return (BG_NER_DIR / "config.json").is_file() and (GLINER_DIR / "gliner_config.json").is_file()


@lru_cache(maxsize=1)
def _bg_ner():
    from transformers import pipeline

    return pipeline("token-classification", model=str(BG_NER_DIR), aggregation_strategy="simple")


@lru_cache(maxsize=1)
def _gliner():
    from gliner import GLiNER

    return GLiNER.from_pretrained(str(GLINER_DIR), local_files_only=True)


def _chunks(text: str, max_chars: int = NER_MAX_CHARS, overlap: int = NER_OVERLAP_CHARS
            ) -> list[tuple[int, str]]:
    """Whitespace-boundary windows of <= max_chars with `overlap`, each as (abs_start, substring).
    Terminates (start strictly increases each step); hard-caps at max_chars when no space exists in the
    window (recall-safe: never over-length, never hangs — a pathological unbroken run is split, and the
    overlap recovers any realistic entity). Short text (<= max_chars) → a single (0, text) window, so
    behaviour is identical to a single pass for short calls."""
    if len(text) <= max_chars:
        return [(0, text)]
    chunks: list[tuple[int, str]] = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            # Back off to the last space so a word isn't split — but only search the LATTER half of the
            # window, so the window stays >= max_chars//2 full. This bounds the window count at
            # ~2n/max_chars: without the lower bound, a stale space near `start` could shrink the window
            # to a few chars and degrade a long low-space run into O(n) tiny windows (O(n) model calls).
            # If no space in the latter half, hard-cap at `end`; the 150-char overlap recovers any word
            # the hard-cap splits.
            ws = text.rfind(" ", start + max_chars // 2, end)
            if ws > start:
                end = ws
        chunks.append((start, text[start:end]))
        if end >= n:
            break
        start = max(start + 1, end - overlap)  # strict forward progress → termination
    return chunks


def ner_spans(text: str) -> list[Span]:
    """Union of BG-NER and GLiNER entity spans (names/addresses/orgs). Raises if a model can't load.
    Long transcripts are windowed (_chunks): both models truncate a single forward pass, so a name
    spoken late in a long call would leak. Per-chunk offsets are translated by the window's absolute
    start so spans resolve to the correct audio times downstream (redact.spans_to_time_ranges)."""
    bg = _bg_ner()      # load once; a missing/unloadable model raises HERE (fail-closed → HOLD, A6)
    gliner = _gliner()
    # Match any person/location/address/facility/org tag scheme (PER/PERSON, LOC/LOCATION, GPE, FAC,
    # ORG, MISC) — recall bias; don't silently drop address entities like GPE/FAC.
    pii_tags = ("PER", "LOC", "GPE", "FAC", "ORG", "MISC")
    spans: list[Span] = []
    for base, chunk in _chunks(text):
        for ent in bg(chunk):
            group = str(ent.get("entity_group") or ent.get("entity") or "").upper()
            if any(tag in group for tag in pii_tags):
                spans.append(Span(base + int(ent["start"]), base + int(ent["end"]), f"NER_{group}"))
        for ent in gliner.predict_entities(chunk, GLINER_LABELS):
            spans.append(Span(base + int(ent["start"]), base + int(ent["end"]), "GLINER_PII"))
    return spans
