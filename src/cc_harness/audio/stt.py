"""Offline STT for redaction detection — in-process faster-whisper against a vendored model.

Used to transcribe each RAW channel ephemerally so PII can be located (plan §0.6). Offline (NFR-7):
the model is a local vendored path; no network at inference. The transcript is caller-owned and must be
discarded after detection (never persisted downstream).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

DEFAULT_MODEL = Path(os.path.expanduser("~/.callcenter-harness/models/faster-whisper-small"))


def transcribe_words(
    audio_path: str, language: str = "bg", model_dir: str | None = None, compute_type: str = "int8"
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return (words, info). words: [{start,end,word,probability}] flattened across segments."""
    md = Path(model_dir or DEFAULT_MODEL)
    if not md.is_dir():
        raise FileNotFoundError(f"STT model not vendored: {md} (run the air-gapped STT provision)")
    from faster_whisper import WhisperModel

    model = WhisperModel(str(md), device="cpu", compute_type=compute_type)
    segments, info = model.transcribe(audio_path, language=language, word_timestamps=True, vad_filter=True)
    words: list[dict[str, Any]] = []
    probs: list[float] = []
    for seg in segments:
        for w in seg.words or []:
            # seg_start/seg_end let the redactor fall back to segment-level ranges for number runs,
            # whose per-word (digit) timestamps are unreliable (redaction research §5a).
            words.append({
                "start": w.start, "end": w.end, "word": w.word, "probability": w.probability,
                "seg_start": seg.start, "seg_end": seg.end,
            })
            probs.append(float(w.probability or 0.0))
    return words, {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "mean_word_probability": (sum(probs) / len(probs)) if probs else 0.0,
        "word_count": len(words),
    }
