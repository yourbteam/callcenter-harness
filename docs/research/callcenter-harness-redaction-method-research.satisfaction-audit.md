# Satisfaction Audit — callcenter-harness-redaction-method-research.md

Loop: `requirements-satisfaction-gap-loop` (depth gate 3 of 3). Question: does each addressed mechanism
actually hold against the **real runtime** — the words.json we produce, Presidio's real language behavior,
ffmpeg, and the sibling STT stage? Gates 1–2 converged.

## Cycle 1 Assessment

### End-to-End Trace + Lens findings

| req_id | trace / lens | evidence | holds? |
| --- | --- | --- | --- |
| span→time map | producer/consumer | `words.json` word tokens **include a leading space** (`' Алло,'`, `' добре'` — verified this session); doc §3 says join tokens "space-separated" → would double spacing, drift char offsets | **NO → SGAP-001** |
| Presidio bg | config-dependence / silent-inert | Presidio's default recognizer registry is English-tagged; `analyze(language="bg")` runs only recognizers whose `supported_language` includes bg. Doc says "invoked with language=bg" but never says the EGN/phone/etc. recognizers must be **registered for bg** | **NO → SGAP-002** (silent zero detection) |
| per-channel redaction | cross-feature contract | doc §7 assumes per-channel detection; the sibling STT `transcribe_airgapped.py` **downmixes to mono** by default (does not split L/R) | **NO → SGAP-003** |
| ffmpeg many-range enable | runtime | `between(t,a,b)+between(t,c,d)` sums to non-zero when any true → valid OR; chaining is the fallback | holds |
| offline (Presidio/GLiNER/NER vendored) | config | all load local weights (gate-1 grounded) | holds |
| EGN checksum | data-reality | weights/mod-11 verified [3]; catch-all covers checksum-failing STT corruption | holds |

### Blocker Gap Ledger

| gap_id | severity | req | lens | evidence (both sides) | why it breaks | planned fix | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SGAP-001 | blocker | span→time map | producer/consumer | producer: faster-whisper `word`=`' добре'` (leading space); consumer: doc §3 "join space-separated" | double spacing drifts every char offset → Presidio spans map to wrong words → wrong audio masked | §3: concatenate the **raw `word` strings as-is** (they already carry spacing); build the char→word map from those exact strings — add no separators | open |
| SGAP-002 | blocker | Presidio bg | config/silent-inert | Presidio runs only recognizers whose `supported_language` includes the analyze language | English-registered recognizers → `analyze("bg")` detects **nothing**, silently | §3: register every pattern + context recognizer with `supported_language="bg"` (or language-agnostic); NLP engine mapped for bg | open |
| SGAP-003 | blocker | per-channel | cross-feature contract | §7 assumes per-channel; `transcribe_airgapped.py` downmixes to mono | per-channel redaction/attribution can't happen on a mono transcript | §7: S2 must run STT **per channel** — split L/R (ffmpeg) then transcribe each (the script's `--channel` arg + a split step); note the cross-stage dependency | open |

## Cycle 1 Plan

| gap_id | target | edit |
| --- | --- | --- |
| SGAP-001 | §3 | raw-string concatenation for the char map |
| SGAP-002 | §3 | register recognizers for bg |
| SGAP-003 | §7 | per-channel STT prerequisite + split step |

## Cycle 1 Edits

- SGAP-001: §3 — char map now **concatenates raw `word` strings as-is** (tokens already carry leading spaces; no added separators).
- SGAP-002: §3 — added **Language registration (critical)**: recognizers must be registered for `bg` (or language-agnostic) or `analyze("bg")` detects nothing.
- SGAP-003: §7 — added **Cross-stage prerequisite**: S2 must split L/R and transcribe per channel; the STT script currently downmixes to mono.

## Cycle 1 Validation

- `grep` confirms all 5 depth-fix markers; `git diff --check` exit 0.
- Post-edit new-gap pass: raw-concat matches the verified token format; bg-registration has no downside (our text is bg); per-channel split is a named prerequisite the plan wires (STT `--channel` arg exists). No new gaps.

## Cycle 2 Assessment (fresh full pass, no edits)

Re-traced each addressed mechanism against the real runtime: span→time map holds against the verified
`words.json` token format; Presidio bg-registration prevents silent-empty detection; per-channel
redaction's dependency on per-channel STT is now explicit; ffmpeg many-range enable holds; all models
vendored (offline). Blocker depth gaps: **0**. SGAP-001/002/003 closed.

## Final Convergence Check

No-edit cycle; fresh full pass found zero blocker depth gaps.

### Final Readiness Proof

| req | holds end-to-end? | evidence |
| --- | --- | --- |
| span→time map | yes | raw-string concat matches verified faster-whisper token format (§3) |
| Presidio bg detection | yes | recognizers registered for bg → not silently empty (§3) |
| per-channel redaction | yes (dependency named) | STT split-per-channel prerequisite (§7); `--channel` arg exists |
| recall measurement | external dep | labeled set + target (OQ-6) — flagged |

### Convergence Statement

Converged after **1 fix cycle + 1 clean pass**. Depth verified against the real STT output, Presidio's
real language behavior, and ffmpeg. Caught 3 abstraction-vs-reality breaks: token-spacing offset drift
(SGAP-001), Presidio silent-empty on unregistered language (SGAP-002), and the mono-vs-per-channel
cross-stage mismatch (SGAP-003). **All three research hardening gates now green.** Remaining external
dependency: a labeled ground-truth set + residual-PII target (OQ-6) to *measure* recall — not an internal
gap. Ready to feed a Plan.
