"""S3' prosody: per-turn acoustic features → a TEXT feature summary (plan §4.2, requirements FR-3').

The summary is text so the phase-ledger evaluator (S4) can quote exact lines (redaction research / plan
§9 SGAP-001). Features per segment: pace (words/sec) and pause-before from the transcript word
timestamps; mean pitch (F0) and mean energy (intensity dB) via parselmouth over the masked channel.
Offline, no network.
"""

from __future__ import annotations

from typing import Any


def _segment_words(words: list[dict[str, Any]]) -> list[tuple[float, float, list[dict[str, Any]]]]:
    segs: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for w in words:
        key = (round(float(w.get("seg_start", w.get("start", 0.0))), 3),
               round(float(w.get("seg_end", w.get("end", 0.0))), 3))
        segs.setdefault(key, []).append(w)
    return [(s, e, ws) for (s, e), ws in sorted(segs.items())]


def _in_masked(t: float, ranges: list[dict[str, Any]] | None) -> bool:
    """True if time t (s) falls inside any redaction-masked span (silenced PII)."""
    if not ranges:
        return False
    return any(float(r.get("start", 0.0)) <= t < float(r.get("end", 0.0)) for r in ranges)


def channel_summary(wav_path: str, words: list[dict[str, Any]], speaker: str,
                    masked_ranges: list[dict[str, Any]] | None = None) -> list[str]:
    """Return one text line per segment with prosody features. Acoustic features (pitch, energy) are
    computed over REAL speech only: sample times inside `masked_ranges` (redaction-silenced PII spans)
    are skipped, so scrubbing does not depress the tone signal (Milestone-2 T2)."""
    import parselmouth  # offline (pure C++), no network

    snd = parselmouth.Sound(wav_path)
    pitch = snd.to_pitch()
    intensity = snd.to_intensity()

    def mean_pitch(s: float, e: float) -> float:
        vals = []
        t = s
        while t < e:
            if _in_masked(t, masked_ranges):
                t += 0.05
                continue
            f = pitch.get_value_at_time(t)
            if f and f > 0:  # voiced only
                vals.append(f)
            t += 0.05
        return sum(vals) / len(vals) if vals else 0.0

    def mean_intensity(s: float, e: float) -> float:
        vals = []
        t = s
        while t < e:
            if _in_masked(t, masked_ranges):
                t += 0.05
                continue
            try:
                v = intensity.get_value(t)
            except Exception:  # noqa: BLE001 - out-of-range times return nothing
                v = None
            if v and v == v:  # not NaN
                vals.append(v)
            t += 0.05
        return sum(vals) / len(vals) if vals else 0.0

    lines: list[str] = []
    prev_end = 0.0
    for s, e, ws in _segment_words(words):
        dur = max(1e-3, e - s)
        wps = len(ws) / dur
        pause_before = max(0.0, s - prev_end)
        f0 = mean_pitch(s, e)
        energy = mean_intensity(s, e)
        lines.append(
            f"{speaker} turn[{s:.1f}-{e:.1f}s]: pace={wps:.1f}wps pause_before={pause_before:.1f}s "
            f"pitch={f0:.0f}Hz energy={energy:.0f}dB"
        )
        prev_end = e
    return lines
