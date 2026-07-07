#!/usr/bin/env bash
# setup_airgapped_redaction.sh — provision the offline PII-redaction stack for cc_harness S2.
#
# Adds Presidio + Bulgarian NER + GLiNER to the air-gapped STT venv and VENDORS all model weights so
# detection runs offline (NFR-7). Provision is ONLINE; detection later runs air-gapped.
#
#   scripts/setup_airgapped_redaction.sh provision   # install libs + vendor models (one-time, online)
#   scripts/setup_airgapped_redaction.sh verify      # prove models load offline (network black-holed)
#
# Prereq: the STT venv from setup_airgapped_stt.sh (STT_HOME/venv). Config via env:
#   STT_HOME=$HOME/.callcenter-harness
set -euo pipefail

STT_HOME="${STT_HOME:-$HOME/.callcenter-harness}"
VENV_DIR="$STT_HOME/venv"
MODELS="$STT_HOME/models"
PY="$VENV_DIR/bin/python"

log() { printf '\033[1;34m[redact-setup]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[redact-setup:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

cmd_provision() {
  [ -x "$PY" ] || die "STT venv missing at $VENV_DIR — run setup_airgapped_stt.sh provision first"
  log "installing redaction + prosody libs (gliner, transformers, torch, parselmouth)"
  "$PY" -m pip install --quiet "gliner" "transformers" "torch" "praat-parselmouth"
  log "vendoring models (bg-ner, gliner-multi, and GLiNER's base encoder mdeberta-v3-base)"
  MODELS="$MODELS" "$PY" - <<'PY'
import os
from huggingface_hub import snapshot_download
base = os.environ["MODELS"]
# GLiNER's gliner_config.json references microsoft/mdeberta-v3-base; its tokenizer must be cached too,
# or GLiNER phones home at load (the air-gap will otherwise block it).
for repo, dst in [("iarfmoose/roberta-small-bulgarian-ner", "bg-ner"),
                  ("urchade/gliner_multi-v2.1", "gliner-multi")]:
    p = os.path.join(base, dst)
    marker = "gliner_config.json" if dst == "gliner-multi" else "config.json"
    if os.path.exists(os.path.join(p, marker)):
        print("exists", dst); continue
    snapshot_download(repo_id=repo, local_dir=p); print("vendored", dst)
snapshot_download(repo_id="microsoft/mdeberta-v3-base")  # into HF cache for GLiNER's tokenizer
print("vendored mdeberta-v3-base (HF cache)")
PY
  log "provision OK"
}

cmd_verify() {
  log "verify: load both NER models with the network black-holed"
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  HTTP_PROXY="http://127.0.0.1:9" HTTPS_PROXY="http://127.0.0.1:9" ALL_PROXY="http://127.0.0.1:9" \
  MODELS="$MODELS" "$PY" - <<'PY'
import os
base = os.environ["MODELS"]
from transformers import pipeline
ner = pipeline("token-classification", model=os.path.join(base, "bg-ner"), aggregation_strategy="simple")
_ = ner("Здравейте")
from gliner import GLiNER
g = GLiNER.from_pretrained(os.path.join(base, "gliner-multi"), local_files_only=True)
_ = g.predict_entities("Здравейте", ["име"])
print("VERIFY PASS: BG-NER + GLiNER loaded and ran offline")
PY
}

case "${1:-}" in
  provision) cmd_provision ;;
  verify)    cmd_verify ;;
  *) echo "usage: $0 {provision|verify}"; exit 1 ;;
esac
