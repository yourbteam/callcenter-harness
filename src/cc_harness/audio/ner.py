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


def ner_spans(text: str) -> list[Span]:
    """Union of BG-NER and GLiNER entity spans (names/addresses/orgs). Raises if a model can't load."""
    spans: list[Span] = []
    # Match any person/location/address/facility/org tag scheme (PER/PERSON, LOC/LOCATION, GPE, FAC,
    # ORG, MISC) — recall bias; don't silently drop address entities like GPE/FAC.
    pii_tags = ("PER", "LOC", "GPE", "FAC", "ORG", "MISC")
    for ent in _bg_ner()(text):
        group = str(ent.get("entity_group") or ent.get("entity") or "").upper()
        if any(tag in group for tag in pii_tags):
            spans.append(Span(int(ent["start"]), int(ent["end"]), f"NER_{group}"))
    gliner = _gliner()
    for ent in gliner.predict_entities(text, GLINER_LABELS):
        spans.append(Span(int(ent["start"]), int(ent["end"]), "GLINER_PII"))
    return spans
