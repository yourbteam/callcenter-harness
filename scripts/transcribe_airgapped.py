#!/usr/bin/env python3
"""Air-gapped Bulgarian transcription with self-hosted faster-whisper.

Runs fully offline against a *vendored* (pre-downloaded) CTranslate2 Whisper model.
No network is required or used at inference time (NFR-7): the model path is local and
HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE are forced on. Emits word-level timestamps, which the
downstream GDPR-redaction stage needs to map detected PII spans back to audio.

Usage:
    python3 transcribe_airgapped.py --model-dir <vendored_model_dir> --audio <file> \
        --out-dir <dir> [--language bg] [--compute-type int8] [--channel left|right]

Outputs (in --out-dir, basename of audio):
    <name>.transcript.txt   plain diarization-agnostic transcript
    <name>.words.json       segments + word-level timestamps + metadata
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Force offline BEFORE importing anything that might touch the network.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def _fail(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    parser = argparse.ArgumentParser(description="Air-gapped faster-whisper transcription.")
    parser.add_argument("--model-dir", required=True, help="Local vendored CTranslate2 model directory.")
    parser.add_argument("--audio", required=True, help="Input audio file.")
    parser.add_argument("--out-dir", required=True, help="Output directory.")
    parser.add_argument("--language", default="bg", help="Language code (default: bg).")
    parser.add_argument("--compute-type", default="int8", help="CTranslate2 compute type (default: int8 for CPU).")
    parser.add_argument("--device", default="cpu", help="Device (cpu/cuda; default cpu).")
    parser.add_argument("--channel", choices=["left", "right"], default=None,
                        help="Transcribe only one stereo channel (for channel-separated diarization).")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    audio = Path(args.audio)
    out_dir = Path(args.out_dir)
    if not model_dir.is_dir():
        _fail(f"Vendored model dir not found: {model_dir}. Run the provision phase first.")
    if not audio.is_file():
        _fail(f"Audio file not found: {audio}")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from faster_whisper import WhisperModel
    except ModuleNotFoundError:
        _fail("faster-whisper not installed. Run the provision phase first.")

    # Local path only; never a bare model name (which could trigger a download).
    model = WhisperModel(str(model_dir), device=args.device, compute_type=args.compute_type)

    # If a single channel is requested, decode it via faster-whisper's built-in ffmpeg (PyAV).
    # faster-whisper downmixes to mono by default; channel isolation is handled upstream by the
    # bash wrapper (which writes a per-channel wav), so here we just transcribe the given file.
    segments, info = model.transcribe(
        str(audio),
        language=args.language,
        word_timestamps=True,
        vad_filter=True,
    )

    seg_list = []
    text_parts = []
    for seg in segments:
        words = [
            {"start": w.start, "end": w.end, "word": w.word, "probability": w.probability}
            for w in (seg.words or [])
        ]
        seg_list.append({
            "id": seg.id,
            "start": seg.start,
            "end": seg.end,
            "text": seg.text,
            "words": words,
        })
        text_parts.append(seg.text.strip())

    name = audio.stem + (f".{args.channel}" if args.channel else "")
    (out_dir / f"{name}.transcript.txt").write_text("\n".join(text_parts) + "\n", encoding="utf-8")
    (out_dir / f"{name}.words.json").write_text(
        json.dumps(
            {
                "audio": str(audio),
                "model_dir": str(model_dir),
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "channel": args.channel,
                "segments": seg_list,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"OK: transcribed {audio.name} -> {out_dir}/{name}.transcript.txt "
          f"(lang={info.language} p={info.language_probability:.2f} dur={info.duration:.1f}s, "
          f"{len(seg_list)} segments)")


if __name__ == "__main__":
    main()
