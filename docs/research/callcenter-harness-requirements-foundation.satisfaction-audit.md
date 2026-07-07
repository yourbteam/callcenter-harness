# Satisfaction Audit — callcenter-harness-requirements-foundation.md

Loop: `requirements-satisfaction-gap-loop` (depth gate 3 of 3). Question: will each addressed
requirement actually hold end-to-end against the **real UP runtime** we plan to reuse? Evidence source:
`/Users/kamenkamenov/united-partners` code (not the doc). Gates 1–2 already converged.

## Cycle 1 Assessment

### Requirement Inventory (addressed reqs with a real UP-runtime / audio dependency)

| req_id | requirement | type | source (quoted) |
| --- | --- | --- | --- |
| R1/R2/R3 | script-adherence scoring via reused phase_ledger_loop | stated | doc §9, FR-4.2 |
| R4/R6 | intonation/emotion + active listening from prosody, scored in S4 | stated | doc §3.4, FR-3', FR-4.4/4.5 |
| R13-R22 | branch-dependent rubric scoring (per call-path mandatory set) | stated | doc §6 design implication, FR-4.1 |
| R28 | auditability via exact-quote traceability | invariant | doc NFR-5 |
| R29 | team-leader feedback + rerun | stated | doc FR-X.1 |
| INV-artifact | audio/prosody passed as file-path refs in run.context | implied-essential | doc §9 |

### End-to-End Trace Table

| req_id | trace | runtime evidence | holds? |
| --- | --- | --- | --- |
| R1/R2/R3 | transcript (S3 text) → phase_ledger producer extracts items w/ exact source_quote → verifier/critic → score | `manager.py:118-143` produce; `:178-187` exact-quote validation; source text-only `runner.py:426-433` | **holds** for transcript-sourced adherence |
| R4/R6 | prosody features → S4 producer item needs `source_quote` ∈ source_text | prosody is numeric; `manager.py:179` `if str(quote) not in source_text` → `manager-invalid-source-quote`; §9 routes prosody as context file-path, which `_source_text_for_phase` never reads (`runner.py:426-433`) | **NO → SGAP-001** |
| R13-R22 | classify call path → score mandatory set for that path | contract `categories`/`minimum_count` are static per contract; `manager.py:188-202` emits `manager-minimum-count` for any category below min, regardless of branch | **NO → SGAP-002** |
| R28 | each item carries exact source_quote; coverage flag | `manager.py:362-370` `exact_source_quote_coverage = exact==total` | **holds** (transcript-sourced) |
| R29 | feedback stored → composed into source_text on rerun | `runner.py:489-493` `_with_feedback`; `_role_executor_for_run` | **holds** |
| INV-artifact | audio phases hand off recording via context path | `_run_ingestion_phase` stores paths+text `runner.py:130-145`; input.source string `config.py:45` | holds **only** for audio-phase handoff, not for feeding the text-only evaluator |

### Lens Coverage Matrix (key lenses)

| req_id | lens | status | evidence |
| --- | --- | --- | --- |
| R4/R6 | cross-feature contract invariant | gap found | evaluator consumes exact text quotes; prosody produces numbers → contract mismatch (SGAP-001) |
| R4/R6 | producer/consumer symmetry | gap found | S3' would emit features; S4 consumer expects quotable text — asymmetric unless S3' emits text |
| R13-R22 | intent vs mechanism | gap found | intent = branch-conditional mandatory set; mechanism = static minimum_count → false failures (SGAP-002) |
| R13-R22 | silent-wrong | gap found | a no-device call would be marked failed for missing device-legal elements |
| R1/R2/R3 | data-reality | checked | transcript IS the source_text; exact quotes valid |
| R28 | end-to-end trace | checked | exact_source_quote_coverage real (manager.py:370) |
| R29 | end-to-end trace | checked | feedback re-enters source_text (runner.py:489-493) |
| INV-artifact | scope-vs-usage reality | gap found (folded into SGAP-001) | file-path-in-context works for audio handoff but not as evaluator input |

### Blocker Gap Ledger

| gap_id | severity | req_id | lens | evidence (both sides) | why it breaks the requirement | planned fix | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SGAP-001 | blocker | R4/R6 | cross-feature invariant / producer-consumer | producer: prosody = numeric features; consumer: `manager.py:178-187,362-370` requires source_quote ∈ text source_text; `runner.py:426-433` sources text-only; doc §9 routes prosody as context file-path | prosody scoring items would fail exact-quote validation → intonation/active-listening unscorable in phase_ledger | lock: S3' emits a **text/JSON prosody-feature summary** as its phase output; S4 uses `input.source: subscribed_phase_outputs` over `subscribes_to: [S3, S3']`; file-path-in-context is only the binary-recording handoff | open |
| SGAP-002 | blocker | R13-R22 | intent vs mechanism / silent-wrong | mechanism: static `categories_detail.minimum_count` enforced unconditionally `manager.py:188-202`; intent: mandatory set varies by call branch | legitimately-absent branch elements trigger false `manager-minimum-count` failures | lock: call-path classification **selects the per-branch contract** (route→contract), and/or branch-applicability is enforced in producer/verifier roles with `minimum_count: 0`, not the deterministic check | open |

## Cycle 1 Plan

### Gap-To-Fix Map

| gap_id | target | edit | validation |
| --- | --- | --- | --- |
| SGAP-001 | §3.4, FR-3'.2, §9 | S3' output = text feature summary; S4 source = subscribed_phase_outputs over S3+S3'; clarify file-path convention scope | re-read; grep "subscribed" + "feature summary" |
| SGAP-002 | §6 design implication, §9, FR-4.1 | branch classification selects the applicable per-branch contract; static minimum_count would false-fail otherwise | re-read; grep "per-branch contract" |

## Cycle 1 Edits

- SGAP-001: FR-3'.2 now emits a **text/JSON feature summary** as S3' output; new FR-3'.3 wires S4 via `input.source: subscribed_phase_outputs` over `subscribes_to:[S3,S3']`; §9 split into binary-handoff (context file-path) vs evaluator-inputs (text, exact-quote-validated) with `manager.py:178-187,362-370` grounding.
- SGAP-002: §9 adds branch-scoring bullet (`manager.py:188-202`); §6 design implication + FR-4.1 now lock **per-branch contract selection** (route→contract) instead of one static contract.

## Cycle 1 Validation

- `grep` confirms FR-3'.3, `subscribed_phase_outputs`, "feature summary", "per-branch contract", and the `manager.py` anchors present. No residual "prosody as file-path" claim. `git diff --check` exit 0.

### Post-Edit New-Gap Pass (Cycle 1)

| changed unit | checked against | result | new gap id |
| --- | --- | --- | --- |
| FR-3'.3 subscribes_to [S3,S3'] | `_compose_subscribed_phase_outputs` raises if a subscribed phase has no output (`runner.py:483-484`) | S3' always emits the summary (FR-3'.2); skipped non-conversation calls don't reach S4 (FR-1.2) — safe | none |
| §9 evaluator-inputs = text | NFR-5 exact_source_quote_coverage | consistent — findings cite exact lines of the composed text source | none |
| per-branch contract | intonation categories (call-universal) | selected per-branch contract also carries the universal intonation categories; or S4 decomposes into adherence + intonation phases — both hold; exact phase count is a plan detail | none |
| §3.4 "feeds into the evaluator" | FR-3'.3 mechanism | now precisely realized; no contradiction | none |

## Cycle 2 Assessment (fresh full pass, no edits)

Re-traced every addressed requirement against the real runtime:

- R1/R2/R3 adherence — holds (transcript is source_text; exact quotes valid, `manager.py:178-187`).
- R4/R6 prosody/intonation/active-listening — **now holds**: S3' text summary + subscribed_phase_outputs makes prosody quotable; SGAP-001 closed.
- R13-R22 branch scoring — **now holds**: per-branch contract selection avoids the static-minimum_count false-fail; SGAP-002 closed.
- R28 auditability — holds (`manager.py:362-370`). R29 feedback/rerun — holds (`runner.py:489-493`).
- INV-artifact — holds with the binary-handoff vs text-evaluator-input split.

Blocker gaps this pass: **0**. SGAP-001, SGAP-002: **closed**.

## Final Convergence Check

No-edit cycle (Cycle 2). Fresh full pass over the addressed requirement set found zero blocker gaps.

### Final Readiness Proof

| req_id | satisfied end-to-end? | evidence |
| --- | --- | --- |
| R1/R2/R3 | yes | phase_ledger exact-quote scoring over transcript (`manager.py:118-203`) |
| R4/R6 | yes | S3' text feature summary + `subscribed_phase_outputs` (doc FR-3'.2/3.3, §9); quotable by evaluator |
| R13-R22 | yes | per-branch contract selection (doc FR-4.1, §6, §9) avoids static-minimum false-fail (`manager.py:188-202`) |
| R28 | yes | `exact_source_quote_coverage` (`manager.py:370`) |
| R29 | yes | feedback re-composed into source_text (`runner.py:489-493`) |
| INV-artifact | yes | binary handoff via context path (`runner.py:130-145`); evaluator inputs are text |

### Convergence Statement

Converged after **1 fix cycle + 1 clean pass**. Depth verified: each addressed requirement holds
against the real UP phase-ledger runtime. Two abstraction-vs-reality breaks were found and closed —
prosody could not reach the exact-quote text evaluator (SGAP-001), and branch-dependent scoring
collided with the static per-category `minimum_count` (SGAP-002). No accepted-scope limitation leaves
any addressed requirement unmet. **All three research hardening gates are now green.**
