# Coverage Audit — callcenter-harness-redaction-method-research.md

Loop: `requirements-coverage-gap-loop` (breadth gate 2 of 3). Question: is the PII set complete and every
PII type + constraint addressed or explicitly scoped out? Requirement source: GDPR personal-data classes
+ `CallScript.docx` content + NFR-6/7, FR-2.3/2.4.

## Cycle 1 Assessment

### Requirement Inventory (PII types + constraints)

| req_id | requirement | type | source |
| --- | --- | --- | --- |
| P1 | Redact EGN | explicit | doc §2; CS L32 |
| P2 | Redact phone/mobile | explicit | doc §2; CS L119 |
| P3 | Redact IBAN/card | explicit | doc §2 |
| P4 | Redact customer name | explicit | doc §2; CS L1/L3 |
| P5 | Redact address | explicit | doc §2; CS L4/L19 |
| P6 | Redact email | explicit | doc §2 |
| P7 | Redact **date of birth** (spoken, distinct from EGN) | implied | GDPR; birthdate may be stated separately |
| P8 | **Account/customer/contract identifiers** (Моят А1 login, customer no., contract no.) | implied | GDPR; CS Моят А1 references |
| C1 | Offline/air-gapped (NFR-7) | non-functional | requirements-foundation NFR-7 |
| C2 | Recall-biased (NFR-6) | non-functional | NFR-6 |
| C3 | Hold on low confidence (FR-2.3) | non-functional | FR-2.3 |
| C4 | Redaction map, no PII values (FR-2.4) | non-functional | FR-2.4 |
| N1 | Must NOT destroy agent audio needed for eval dims 2–3 | negative/boundary | requirements-foundation FR-4.4/4.5 |
| S1 | **Agent identity** — redact or retain? | scope-boundary | CS L1 agent self-ID |
| S2 | **Customer voice** retained in compliant recording (biometric) | scope-boundary | the recording keeps the voice for QA |

### Coverage Matrix (gaps highlighted)

| req.obligation | status | evidence |
| --- | --- | --- |
| P1-P6 | addressed | §2 table |
| P7 (DOB) | **absent** | not enumerated → CGAP-001 |
| P8 (account/contract IDs) | **absent** | not enumerated → CGAP-004 |
| C1-C4 | addressed | §1/§3 (offline), §6 (recall, hold), §3/§9 (map) |
| N1 (agent audio preserved) | **absent/conflict** | §6 says over-mask OK, but never bounds masking on the agent channel that eval dims 2–3 need → CGAP-005 |
| S1 (agent identity) | **neither addressed nor scoped** | → CGAP-002 |
| S2 (voice retention) | **neither addressed nor scoped** | → CGAP-003 |

### Blocker Gap Ledger

| gap_id | severity | req | lens | why uncovered | planned fix | status |
| --- | --- | --- | --- | --- | --- | --- |
| CGAP-001 | blocker | P7 | omission | DOB is separable PII, not enumerated | add DOB row to §2 (date pattern + context "роден/дата на раждане") | open |
| CGAP-002 | blocker | S1 | scope-boundary | agent-identity handling undecided | scope: agent name/ID **retained** (QA needs agent attribution; agent is not the protected data subject here) with rationale | open |
| CGAP-003 | blocker | S2 | scope-boundary | voice biometric retention unstated | explicit accepted-retention: compliant recording keeps the voice (QA needs delivery/emotion; recordings are client-owned) — spoken-PII content is masked, voice is not | open |
| CGAP-004 | blocker | P8 | omission | account/customer/contract IDs not enumerated | add row: account/customer/contract identifiers (numeric-run + context "клиентски номер","договор","Моят А1") | open |
| CGAP-005 | blocker | N1 | conflict/reconciliation | over-mask (NFR-6) vs agent audio needed for dims 2–3 | reconcile: masking is **per-channel**; the customer channel is over-masked freely; agent-channel masking is bounded to actual PII utterances so prosody/active-listening stay assessable | open |

## Cycle 1 Plan

| gap_id | target | edit |
| --- | --- | --- |
| CGAP-001 | §2 table | + DOB row |
| CGAP-004 | §2 table | + account/contract-ID row |
| CGAP-002/003 | new "Scope boundaries" note | agent identity retained; voice retained (rationale) |
| CGAP-005 | §6 or §7 | per-channel masking bound; agent-channel masking limited to actual PII |

## Cycle 1 Edits

- CGAP-001/004: §2 table — added **DOB** and **account/customer/contract ID** rows (pattern + context + NER).
- CGAP-002/003: new **§7a Scope boundaries** — agent identity retained (not the protected subject); customer voice retained in the compliant recording (QA needs it; client-owned) — explicit accepted retentions.
- CGAP-005: §7 **Masking bound** — per-channel; customer channel over-masked freely; agent channel masking bounded to the agent reciting customer PII (agent self-ID retained) so eval dims 2–3 stay assessable.

## Cycle 1 Validation

- `grep` confirms all six edit markers present; unresolved-term scan clean; `git diff --check` exit 0.
- Post-edit new-gap pass: agent-channel PII (agent reciting customer name/address, CS L4) is still masked (recall preserved); "agent identity retained" tightened to distinguish agent self-ID from recited customer PII. No new conflict.

## Cycle 2 Assessment (fresh full pass, no edits)

Re-elicited the PII set + constraints. P1–P8 each have a detection mechanism (§2); C1–C4 addressed;
N1 reconciled (per-channel masking bound); S1/S2 explicitly scoped with rationale (§7a). Acceptance
criterion for all detection: recall ≥ target on a labeled set (§8, OQ-6) — a single global testable
criterion, external-data-dependent (flagged, not a coverage hole). Blocker coverage gaps: **0**.

## Final Convergence Check

No-edit cycle; fresh full pass found zero blocker coverage gaps.

### Final Coverage Proof

| req | covered/scoped? | acceptance criterion | evidence |
| --- | --- | --- | --- |
| P1-P8 | covered | recall ≥ target on labeled set (OQ-6) | §2 table |
| C1-C4 | covered | offline run / recall-bias / hold / map-shape | §1,§3,§6,§9 |
| N1 | covered (reconciled) | agent-channel speech remains scorable | §7 masking bound |
| S1,S2 | scoped-out w/ rationale | n/a | §7a |

### Convergence Statement

Converged after **1 fix cycle + 1 clean pass**. Breadth only — every PII type + constraint addressed or
explicitly scoped. Intentional exclusions: agent identity (retained), customer voice (retained). Recall
target + labeled ground-truth set remain external dependencies (OQ-6). Next: gate 3
`requirements-satisfaction-gap-loop` (depth).
