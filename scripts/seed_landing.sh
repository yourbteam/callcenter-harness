#!/usr/bin/env bash
# seed_landing.sh — clone source call recordings into the SECURE LANDING AREA.
#
# Simulates ingestion of "originals" into a controlled zone. The harness then treats the file in the
# landing area as THE original; after a verified-successful scrub, a separate cleanup step deletes that
# original (+ raw ingest splits), so PII-bearing audio exists only transiently. This script only SEEDS.
#
#   scripts/seed_landing.sh seed     # clone SRC audio -> LANDING (idempotent; checksum-verified)
#   scripts/seed_landing.sh list     # list what is currently in the landing area
#   scripts/seed_landing.sh verify   # confirm every seeded file matches its source by checksum
#
# Config via env:
#   SRC=$HOME/Downloads/audio-files          # source of "original" recordings (simulated upload)
#   LANDING=$HOME/.callcenter-harness/landing # secure landing area (gitignored, air-gapped zone)
set -uo pipefail
SRC="${SRC:-$HOME/Downloads/audio-files}"
LANDING="${LANDING:-$HOME/.callcenter-harness/landing}"
log() { printf '\033[1;34m[seed]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[seed:FAIL]\033[0m %s\n' "$*" >&2; exit 1; }

_audio() { find "$1" -maxdepth 1 -type f \( -iname '*.mp3' -o -iname '*.wav' \) 2>/dev/null; }
_sum() { shasum -a 256 "$1" | awk '{print $1}'; }

cmd_seed() {
  [ -d "$SRC" ] || die "source dir not found: $SRC"
  [ "$(_audio "$SRC" | wc -l | tr -d ' ')" -gt 0 ] || die "no .mp3/.wav in $SRC"
  mkdir -p "$LANDING"
  local n=0
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    local base dst; base="$(basename "$f")"; dst="$LANDING/$base"
    if [ -f "$dst" ] && [ "$(_sum "$f")" = "$(_sum "$dst")" ]; then
      log "already seeded (checksum match): $base"; continue
    fi
    cp -f "$f" "$dst"
    [ "$(_sum "$f")" = "$(_sum "$dst")" ] || die "checksum mismatch after copy: $base"
    log "seeded: $base ($(du -h "$dst" | cut -f1))"; n=$((n+1))
  done < <(_audio "$SRC")
  log "seed OK. $n new file(s) into $LANDING (total $(_audio "$LANDING" | wc -l | tr -d ' '))."
}

cmd_list() { log "landing area: $LANDING"; _audio "$LANDING" | sed "s#$HOME#~#" || true; }

cmd_verify() {
  local ok=1
  while IFS= read -r dst; do
    [ -n "$dst" ] || continue
    local base src; base="$(basename "$dst")"; src="$SRC/$base"
    if [ ! -f "$src" ]; then log "no source for $base (source may have been removed) — skip"; continue; fi
    if [ "$(_sum "$src")" = "$(_sum "$dst")" ]; then log "OK  $base"; else log "MISMATCH $base"; ok=0; fi
  done < <(_audio "$LANDING")
  [ "$ok" = 1 ] && log "VERIFY PASS: all seeded files match their source" || die "VERIFY FAIL: checksum mismatch"
}

case "${1:-}" in
  seed)   cmd_seed ;;
  list)   cmd_list ;;
  verify) cmd_verify ;;
  *) echo "usage: $0 {seed|list|verify}"; exit 1 ;;
esac
