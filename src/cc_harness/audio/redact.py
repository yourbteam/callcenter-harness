"""S2 redaction: detect PII in a word-timestamped transcript and mask the audio (plan §3.2).

Detection is recall-biased (NFR-6): a hit from ANY recognizer masks; number runs are caught even when
the EGN/Luhn checksum fails (STT can corrupt a digit). Detection runs over the RAW concatenation of the
faster-whisper `word` tokens (they already carry a leading space — see redaction research §3), with a
char-offset→word-index map so spans resolve to word `start/end` audio times. NER (names/addresses) is a
pluggable hook (added when the offline models are vendored); the pattern + context recognizers here need
no ML and cover the structured/high-risk PII.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

EGN_WEIGHTS = [2, 4, 8, 5, 10, 9, 7, 3, 6]

# Lead-in phrases after which the following tokens are likely PII (grounded in CallScript phrasing).
CONTEXT_LEAD_INS = [
    "на адрес", "адрес", "егн", "е.г.н", "г-н", "г-жа", "господин", "госпожо",
    "телефон", "мобилен", "номер", "клиентски номер", "договор", "абонатен",
]


@dataclass(frozen=True)
class Span:
    start: int  # char offset into the concatenated text (inclusive)
    end: int    # char offset (exclusive)
    category: str


def egn_checksum_ok(digits: str) -> bool:
    if len(digits) != 10 or not digits.isdigit():
        return False
    total = sum(int(digits[i]) * EGN_WEIGHTS[i] for i in range(9))
    check = total % 11
    if check == 10:
        check = 0
    return check == int(digits[9])


def luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or len(digits) < 13:
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def build_text_and_map(words: list[dict[str, Any]]) -> tuple[str, list[int]]:
    """Concatenate raw `word` strings as-is; return (text, char_to_word_index)."""
    parts: list[str] = []
    char_to_word: list[int] = []
    for i, w in enumerate(words):
        token = str(w.get("word", ""))
        parts.append(token)
        char_to_word.extend([i] * len(token))
    return "".join(parts), char_to_word


def _classify_number(digits: str) -> str:
    if len(digits) == 10 and egn_checksum_ok(digits):
        return "EGN"
    if luhn_ok(digits) and 13 <= len(digits) <= 19:
        return "CARD"
    if 7 <= len(digits) <= 13:
        return "PHONE_OR_ID"
    return "NUMERIC_RUN"  # catch-all — masked regardless (recall bias)


def find_pattern_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    # BG IBAN: BG + 2 check digits + 18 alphanumerics.
    for m in re.finditer(r"\bBG\d{2}[A-Z0-9]{18}\b", text, re.IGNORECASE):
        spans.append(Span(m.start(), m.end(), "IBAN"))
    # Number runs: >=5 digit-ish chars, allowing internal spaces/dashes (spoken digit groups).
    for m in re.finditer(r"\d[\d \-]{3,}\d", text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) >= 5:
            spans.append(Span(m.start(), m.end(), _classify_number(digits)))
    return spans


def find_context_spans(text: str, follow_chars: int = 40) -> list[Span]:
    """Mask a window after each lead-in phrase (names/addresses spoken after known cues)."""
    spans: list[Span] = []
    low = text.lower()
    for lead in CONTEXT_LEAD_INS:
        idx = 0
        while True:
            pos = low.find(lead, idx)
            if pos == -1:
                break
            start = pos + len(lead)
            end = min(len(text), start + follow_chars)
            # trim to a sentence boundary if one is closer
            boundary = re.search(r"[.!?\n]", text[start:end])
            if boundary:
                end = start + boundary.start()
            if end > start:
                spans.append(Span(start, end, "CONTEXT_PII"))
            idx = pos + len(lead)
    return spans


# Distinctive agent-script markers (Bulgarian) used only to tell the agent channel from the customer
# channel for the §7 masking bound — the agent recites the script.
SCRIPT_MARKERS = [
    "оферта", "отстъпк", "договор", "месечна такса", "канал", "интернет",
    "обажда", "от името", "записва", "възползвате", "рутер", "евро",
]


def pick_agent_channel(channel_texts: dict[str, str]) -> str | None:
    """Agent = channel with the most script-marker hits. None if all channels score 0."""
    scored = {chan: sum(text.lower().count(m) for m in SCRIPT_MARKERS) for chan, text in channel_texts.items()}
    best = max(scored, key=lambda c: scored[c]) if scored else None
    return best if best is not None and scored[best] > 0 else None


def detect_spans(
    text: str, ner_hook: Callable[[str], list[Span]] | None = None, include_context: bool = True
) -> list[Span]:
    """Union of all recognizers (recall bias). ner_hook adds ML NER spans when available.
    include_context=False drops the broad lead-in window over-masking — used on the AGENT channel (§7
    masking bound) so the agent's script delivery stays assessable; patterns + NER still mask actual
    customer PII the agent recites (names/addresses via NER, numbers/EGN via patterns)."""
    spans = list(find_pattern_spans(text))
    if include_context:
        spans += find_context_spans(text)
    if ner_hook is not None:
        spans.extend(ner_hook(text))
    return spans


# Categories whose spoken digits give unreliable per-word timestamps → mask the whole containing
# segment(s) instead of the word span (redaction research §5a; recall bias).
NUMBER_CATEGORIES = {"EGN", "CARD", "PHONE_OR_ID", "NUMERIC_RUN", "IBAN"}


def spans_to_time_ranges(
    spans: list[Span], words: list[dict[str, Any]], char_to_word: list[int], pad: float = 0.25
) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    for sp in spans:
        widxs = sorted({char_to_word[i] for i in range(sp.start, min(sp.end, len(char_to_word)))})
        widxs = [i for i in widxs if 0 <= i < len(words)]
        if not widxs:
            continue
        first, last = words[widxs[0]], words[widxs[-1]]
        if sp.category in NUMBER_CATEGORIES:
            # Segment-level fallback: cover the whole segment(s) the number run touches.
            start = float(first.get("seg_start", first.get("start", 0.0))) - pad
            end = float(last.get("seg_end", last.get("end", 0.0))) + pad
        else:
            start = float(first.get("start", 0.0)) - pad
            end = float(last.get("end", 0.0)) + pad
        ranges.append({"start": max(0.0, start), "end": max(0.0, end), "category": sp.category})
    return _merge_ranges(ranges)


def _merge_ranges(ranges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not ranges:
        return []
    ordered = sorted(ranges, key=lambda r: r["start"])
    merged = [dict(ordered[0])]
    for r in ordered[1:]:
        last = merged[-1]
        if r["start"] <= last["end"]:
            last["end"] = max(last["end"], r["end"])
            if r["category"] != last["category"]:
                last["category"] = "MULTI"
        else:
            merged.append(dict(r))
    return merged


def _run_ffmpeg_checked(cmd: list[str], what: str) -> None:
    """Run ffmpeg and RAISE on failure — a silent mask failure must never yield an unmasked
    'compliant' recording (fail-closed; the redaction phase turns this into a HOLD)."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg {what} failed (rc={proc.returncode}): {proc.stderr.strip()[-300:]}")


def mask_audio(in_path: str, out_path: str, ranges: list[dict[str, Any]]) -> None:
    if not ranges:
        shutil.copy(in_path, out_path)
        return
    enable = "+".join(f"between(t,{r['start']:.3f},{r['end']:.3f})" for r in ranges)
    _run_ffmpeg_checked(
        ["ffmpeg", "-y", "-hide_banner", "-i", in_path, "-af", f"volume=enable='{enable}':volume=0", out_path],
        "mask",
    )


def combine_channels(left_path: str, right_path: str, out_path: str) -> None:
    """Join two masked mono channels back into the stereo compliant recording."""
    _run_ffmpeg_checked(
        ["ffmpeg", "-y", "-hide_banner", "-i", left_path, "-i", right_path,
         "-filter_complex", "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]", "-map", "[a]", out_path],
        "combine_channels",
    )
