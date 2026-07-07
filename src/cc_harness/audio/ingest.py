"""S1 ingest: probe, non-conversation gate, and channel split (plan §3.1).

Pure ffmpeg/ffprobe; no network. Non-conversation calls (no-answer / voicemail / too short) are gated
out here (FR-1.2) so nothing fabricates a downstream evaluation. Stereo is split L/R for free per-channel
diarization (validated: the sample is dual-channel).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path: str) -> dict[str, Any]:
    """Return {channels, duration_seconds} via ffprobe."""
    r = _run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=channels", "-show_entries", "format=duration",
        "-of", "json", path,
    ])
    data = json.loads(r.stdout or "{}")
    streams = data.get("streams") or [{}]
    channels = int(streams[0].get("channels") or 0)
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    return {"channels": channels, "duration_seconds": duration}


def mean_volume_db(path: str) -> float | None:
    """Overall mean volume (dB) via ffmpeg volumedetect; None if unparseable."""
    r = _run(["ffmpeg", "-hide_banner", "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                return float(line.split("mean_volume:")[1].split("dB")[0].strip())
            except ValueError:
                return None
    return None


def classify_conversation(
    path: str, min_seconds: float = 8.0, silence_db: float = -50.0
) -> tuple[bool, str, dict[str, Any]]:
    """(is_conversation, reason, probe_info). Too-short or near-silent → not a conversation."""
    info = probe(path)
    if info["duration_seconds"] < min_seconds:
        return False, f"too short ({info['duration_seconds']:.1f}s < {min_seconds}s)", info
    mv = mean_volume_db(path)
    info["mean_volume_db"] = mv
    if mv is not None and mv < silence_db:
        return False, f"near-silent (mean {mv:.1f} dB < {silence_db} dB)", info
    return True, "conversation", info


def split_channels(path: str, out_dir: str) -> dict[str, str]:
    """Split stereo into left.wav/right.wav (free diarization). Mono → single mono.wav."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    info = probe(path)
    if info["channels"] < 2:
        mono = out / "mono.wav"
        _run(["ffmpeg", "-y", "-hide_banner", "-i", path, "-ac", "1", str(mono)])
        return {"mono": str(mono)}
    left, right = out / "left.wav", out / "right.wav"
    _run([
        "ffmpeg", "-y", "-hide_banner", "-i", path,
        "-filter_complex", "channelsplit=channel_layout=stereo[l][r]",
        "-map", "[l]", str(left), "-map", "[r]", str(right),
    ])
    return {"left": str(left), "right": str(right)}
