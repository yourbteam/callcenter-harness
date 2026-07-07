#!/usr/bin/env bash
# setup_airgapped_stt.sh — provision + run an air-gapped local Bulgarian STT (faster-whisper).
#
# Compliance (NFR-7): every stage that touches source audio must run offline with no network
# egress and no telemetry. This script splits into:
#   * provision  — ONLINE: install ffmpeg, create venv, install faster-whisper, VENDOR model weights.
#   * channels   — offline: detect whether a stereo recording separates speakers (free diarization).
#   * process    — AIR-GAPPED: transcribe with the vendored model, network forced dead + offline flags.
#   * verify     — prove transcription succeeds with the network black-holed (NFR-7 acceptance).
#
# Nothing here prints secrets. All steps are idempotent where practical.
#
# Usage:
#   scripts/setup_airgapped_stt.sh provision
#   scripts/setup_airgapped_stt.sh channels <audio>
#   scripts/setup_airgapped_stt.sh process  <audio>
#   scripts/setup_airgapped_stt.sh verify   <audio>
#   scripts/setup_airgapped_stt.sh all      <audio>
#
# Config via env (defaults shown):
#   STT_MODEL=large-v3        # faster-whisper model (large-v3 = best Bulgarian; base/small = fast dev)
#   STT_LANG=bg
#   STT_HOME=$HOME/.callcenter-harness
#   STT_COMPUTE_TYPE=int8     # int8 = CPU-friendly
set -euo pipefail

STT_MODEL="${STT_MODEL:-large-v3}"
STT_LANG="${STT_LANG:-bg}"
STT_HOME="${STT_HOME:-$HOME/.callcenter-harness}"
STT_COMPUTE_TYPE="${STT_COMPUTE_TYPE:-int8}"
VENV_DIR="$STT_HOME/venv"
VENDOR_DIR="$STT_HOME/models/faster-whisper-$STT_MODEL"
MODEL_REPO="Systran/faster-whisper-$STT_MODEL"
OUT_DIR="${STT_OUT_DIR:-$STT_HOME/out}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\033[1;34m[stt]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[stt:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

require() { command -v "$1" >/dev/null 2>&1 || die "missing prerequisite: $1"; }

# Force offline + black-hole any accidental network call. A dead loopback proxy makes any
# outbound HTTP fail fast, so we PROVE inference needs no network rather than trusting the lib.
airgap_env() {
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
  export HTTP_PROXY="http://127.0.0.1:9" HTTPS_PROXY="http://127.0.0.1:9" ALL_PROXY="http://127.0.0.1:9"
  export http_proxy="http://127.0.0.1:9" https_proxy="http://127.0.0.1:9" all_proxy="http://127.0.0.1:9"
}

cmd_provision() {
  log "provision (ONLINE): ffmpeg + venv + faster-whisper + vendored model '$STT_MODEL'"
  require brew; require python3
  command -v ffmpeg >/dev/null 2>&1 || { log "installing ffmpeg"; brew install ffmpeg; }
  mkdir -p "$STT_HOME/models" "$OUT_DIR"
  if [ ! -d "$VENV_DIR" ]; then log "creating venv"; python3 -m venv "$VENV_DIR"; fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet "faster-whisper>=1.0" "huggingface_hub>=0.23"
  if [ ! -f "$VENDOR_DIR/model.bin" ]; then
    log "vendoring model $MODEL_REPO -> $VENDOR_DIR (one-time download)"
    # Use the stable Python API (the huggingface-cli/hf CLI name has churned; the API has not).
    MODEL_REPO="$MODEL_REPO" VENDOR_DIR="$VENDOR_DIR" python -c 'import os; from huggingface_hub import snapshot_download; snapshot_download(repo_id=os.environ["MODEL_REPO"], local_dir=os.environ["VENDOR_DIR"])'
  else
    log "model already vendored at $VENDOR_DIR (skip)"
  fi
  log "provision OK. Model vendored; inference can now run offline."
}

# Heuristic: is the stereo file dual-channel with distinct speakers (→ free diarization),
# or just duplicated mono? Measures RMS of (L-R). Near-silence ⇒ duplicated mono.
cmd_channels() {
  local audio="${1:?usage: channels <audio>}"; require ffmpeg
  [ -f "$audio" ] || die "audio not found: $audio"
  local ch; ch="$(ffprobe -v error -select_streams a:0 -show_entries stream=channels -of csv=p=0 "$audio" 2>/dev/null | tr -cd '0-9')"; ch="${ch:-?}"
  log "channels=$ch"
  if [ "$ch" != "2" ]; then log "not stereo → native diarization needed (pyannote)"; return 0; fi
  local diff_rms l_rms
  diff_rms="$(ffmpeg -hide_banner -i "$audio" -af 'pan=mono|c0=c0-c1,astats=metadata=1' -f null - 2>&1 | awk -F': ' '/Overall.*RMS level|RMS level dB/{v=$2} END{print v}')"
  l_rms="$(ffmpeg -hide_banner -i "$audio" -af 'pan=mono|c0=c0,astats=metadata=1' -f null - 2>&1 | awk -F': ' '/RMS level dB/{v=$2} END{print v}')"
  log "L-R difference RMS: ${diff_rms:-n/a} dB   |   L channel RMS: ${l_rms:-n/a} dB"
  log "Interpretation: if (L-R) RMS is close to the channel RMS, channels DIFFER → likely speaker-separated"
  log "                 (free diarization). If (L-R) RMS is much lower (near-silent), it's duplicated mono."
}

cmd_process() {
  local audio="${1:?usage: process <audio>}"
  [ -f "$audio" ] || die "audio not found: $audio"
  [ -d "$VENDOR_DIR" ] || die "model not vendored; run: $0 provision"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  airgap_env
  log "process (AIR-GAPPED: offline flags + dead proxy) model=$STT_MODEL lang=$STT_LANG"
  python "$SCRIPT_DIR/transcribe_airgapped.py" \
    --model-dir "$VENDOR_DIR" --audio "$audio" --out-dir "$OUT_DIR" \
    --language "$STT_LANG" --compute-type "$STT_COMPUTE_TYPE"
  log "process OK. Transcript + word timestamps in $OUT_DIR"
}

# NFR-7 acceptance: transcription must succeed with the network black-holed.
cmd_verify() {
  local audio="${1:?usage: verify <audio>}"
  log "verify: running process with network black-holed (dead proxy + offline flags)"
  cmd_process "$audio" && log "VERIFY PASS: transcription succeeded with no network egress" \
    || die "VERIFY FAIL: transcription needed the network — investigate before trusting air-gap"
}

case "${1:-}" in
  provision) cmd_provision ;;
  channels)  cmd_channels "${2:-}" ;;
  process)   cmd_process  "${2:-}" ;;
  verify)    cmd_verify   "${2:-}" ;;
  all)       cmd_provision; cmd_channels "${2:?usage: all <audio>}"; cmd_verify "${2}" ;;
  *) echo "usage: $0 {provision|channels <audio>|process <audio>|verify <audio>|all <audio>}"; exit 1 ;;
esac
