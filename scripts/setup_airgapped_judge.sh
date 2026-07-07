#!/usr/bin/env bash
# setup_airgapped_judge.sh — provision the offline LLM judge for cc_harness command-mode eval.
# Installs Ollama (brew), starts the loopback server, pulls a Bulgarian-capable instruct model.
# Provision is ONLINE (one-time); judging then runs offline (loopback only, NFR-7).
#
#   scripts/setup_airgapped_judge.sh provision   # brew install + serve + pull model
#   scripts/setup_airgapped_judge.sh verify      # prove the judge answers on loopback
# Config via env:  JUDGE_MODEL=qwen2.5:32b   OLLAMA_HOST=http://127.0.0.1:11434
set -uo pipefail
JUDGE_MODEL="${JUDGE_MODEL:-qwen2.5:32b}"
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log(){ printf '\033[1;34m[judge]\033[0m %s\n' "$*"; }
die(){ printf '\033[1;31m[judge:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

wait_up(){ for _ in $(seq 1 30); do curl -sf "$OLLAMA_HOST/api/tags" >/dev/null 2>&1 && return 0; sleep 1; done; return 1; }

cmd_provision(){
  command -v brew >/dev/null || die "brew required"
  command -v ollama >/dev/null 2>&1 || { log "installing ollama"; brew install ollama || die "brew install ollama failed"; }
  if ! wait_up; then log "starting ollama server"; (brew services start ollama >/dev/null 2>&1 || nohup ollama serve >/tmp/ollama.serve.log 2>&1 &) ; fi
  wait_up || die "ollama server not reachable at $OLLAMA_HOST"
  log "server up at $OLLAMA_HOST"
  if ollama list 2>/dev/null | grep -q "${JUDGE_MODEL%%:*}"; then
    log "model matching '${JUDGE_MODEL%%:*}' already present (skip pull)"
  else
    log "pulling $JUDGE_MODEL (one-time, ~GBs)"; ollama pull "$JUDGE_MODEL" || die "ollama pull $JUDGE_MODEL failed"
  fi
  ollama list | sed -n '1,10p'
  log "provision OK. Judge model vendored; command-mode eval can run offline (loopback)."
}

cmd_verify(){
  wait_up || die "ollama server not reachable — run: $0 provision"
  log "verify: round-trip a tiny judge call on loopback (no external egress)"
  printf 'Reply with a JSON object {"ok": true} and nothing else.' | \
    NO_PROXY=127.0.0.1 JUDGE_MODEL="$JUDGE_MODEL" python3 "$SCRIPT_DIR/judge_ollama.py" --selftest \
    && log "VERIFY PASS: judge answered on loopback offline" \
    || die "VERIFY FAIL: judge did not answer"
}

case "${1:-}" in
  provision) cmd_provision ;;
  verify)    cmd_verify ;;
  *) echo "usage: $0 {provision|verify}"; exit 1 ;;
esac
