# Coverage Audit — callcenter-harness-requirements-foundation.md

Loop: `requirements-coverage-gap-loop` (breadth gate 2 of 3). Question: is the requirement set
complete, and is every requirement (decomposed into obligations) addressed by the doc or explicitly
scoped out with a testable criterion? Sources: `ClientFiles/FirstWorkflow.md` (FW),
`ClientFiles/CallScript.docx` (CS).

## Cycle 1 Assessment

### Requirement Inventory

| req_id | requirement | type | source (quoted) |
| --- | --- | --- | --- |
| R1 | Score script adherence (mandatory elements said) | explicit | FW L7 "скрипт, който следва със задължителни елементи"; L23 |
| R2 | Mandatory phrasings said the specific way; forbidden words not used | explicit | FW L13 "думички които задължително се казват по точно определен начин, има и думи които не се използват" |
| R3 | Enforce order: start Offer 1, rebut objections, then next offer | explicit | FW L9 "да се започва от оферта 1, да се оборват възражения и чак след това… следваща оферта" |
| R4 | Score agent intonation/emotion (confidence, smile, diction) | explicit | FW L9 |
| R5 | Recognize customer emotion | explicit (later) | FW L11 "разпознаваме и емоцията и на клиента… (това после)" |
| R6 | Score active listening | explicit | FW L23 "активнослушане" |
| R7 | Track call duration | explicit | FW L15 "времетраене на разговора" |
| R8 | Track result/outcome | explicit | FW L15 "резултат" |
| R9 | Detect success template / call break-point | explicit | FW L15 "има ли темплейт… или специфично място където се чупят" |
| R10 | Detect named failure patterns (7) | explicit | FW L17 (sluggish; lose customer early; give up; not repeat offer; not praise; not give benefits; not ask for decision) |
| R11 | Agent post-call data entry (order/address/comment/result) | explicit | FW L19 "нанасяне на данни… поръчка, адрес, коментар, резултат" |
| R12 | Offers are individualized per client | explicit | FW L5 "индивидуални предложения за всеки клиент" |
| R13 | Opening + record-consent disclosure | explicit | CS L1-3 |
| R14 | Offer 1 full content | explicit | CS L4-24 |
| R15 | Cross-sell MBB/Netbox mandatory card check + branch | explicit | CS L32-40 |
| R16 | Offer 2 / Offer 3 escalation ladder | explicit | CS L25-27 |
| R17 | Mandatory post-acceptance questions | explicit | CS L29 |
| R18 | Objection-bank prescribed rebuttals | explicit | CS L45-112 |
| R19 | "Cents-per-day" reframing device | explicit | CS L87-98 |
| R20 | Legal-part disclosures (5 variants) | explicit | CS L116-202 |
| R21 | Mandatory closing recap | explicit | CS L128-131 |
| R22 | Call-type variants incl. repeat/decision callback | explicit | CS L104 "При повторно обаждане за решение" |
| R23 | Bulgarian STT | non-functional | derived; CS/FW in Bulgarian |
| R24 | GDPR-redact before any downstream use (negative: no un-redacted audio downstream) | non-functional/negative | client flow this session; NFR-2 |
| R25 | Redaction must favor recall (over-redact) — a missed EGN = compliance breach | non-functional (safety) | derived from "focus is on compliance" (this session) + CS L32 EGN |
| R26 | Process dialer-scale volume asynchronously | non-functional | FW L5 auto-dialer |
| R27 | Handle low-confidence STT without fabricating authority | non-functional | derived |
| R28 | Auditability: findings trace to exact quotes | non-functional | derived; NFR-5 |
| R29 | Team-leader review + rerun of evaluations | implied | FW L15 team leaders |
| R30 | Handle non-conversation calls (no answer, voicemail, aborted) | negative/boundary | derived from auto-dialer L5 |
| R31 | Per-call QA report output | implied | FW L15 monitoring |

### Coverage Matrix (obligation-level; gaps highlighted)

| req.obligation | status | addressed where / rationale |
| --- | --- | --- |
| R1 | addressed | §5, §6, FR-4.2 |
| R2.forbidden-words **source** | **absent** | FR-4.2 flags forbidden words, but CS contains no forbidden-words list; no input requirement enumerates it → CGAP-001 |
| R2.verbatim-vs-paraphrase | **partial** | FR-4.2 "required phrasings honored" — no criterion distinguishing must-say-verbatim from paraphrasable → CGAP-002 |
| R3 | addressed | FR-4.2 order clause |
| R4 | addressed | §3.4, FR-3', FR-4.4 |
| R5 | out-of-scope (later) | §11 W5 |
| R6 | addressed | FR-4.5 |
| R7 | addressed | FR-4.7 |
| R8.outcome | addressed (value); taxonomy deferred | FR-4.7; outcome set → OQ-5 |
| R9 | addressed | FR-4.6, FR-X.2 |
| R10.each-of-7 | addressed (set) | FR-4.6 "flag the named patterns in §5 (L17)" |
| R11.evaluate-data-entry | **neither addressed nor scoped** | §5 "candidate cross-checks"; FR-1.1 OQ-5 — not decided in/out → CGAP-006 |
| R12.correct-individualized-values | **absent** | doc scores element presence, not whether stated price/channels/Mbps match this client's offer; no per-client offer-data input → CGAP-004 |
| R13-R21 | addressed | §6.1-6.9 |
| R22.call-type | **partial** | FR-4.1 classifies offer/sign/device/cross-sell, not first-contact vs callback → CGAP-003 |
| R23 | addressed | NFR-1, FR-3.1 |
| R24 | addressed | §4 gate, FR-2.2/2.3 |
| R25.redaction-recall-bias | **absent** | FR-2.3 holds on low confidence, but no requirement to bias toward over-redaction → CGAP-005 |
| R26 | addressed | NFR-3 |
| R27 | addressed | NFR-4 |
| R28 | addressed | NFR-5 |
| R29 | addressed | FR-X.1 |
| R30.non-conversation | **absent** | pipeline assumes a real dialogue; no skip/flag path → CGAP-007 |
| R31 | addressed | FR-4.7 |

### Blocker Gap Ledger

| gap_id | severity | req.obligation | lens | evidence | why uncovered | planned fix | closure evidence | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CGAP-001 | blocker | R2.forbidden-words-source | elicitation/omission | FR-4.2 (L147-150) requires forbidden-word flagging; CS has no such list | harness needs a client-provided forbidden-words list; no input requirement or OQ enumerates it | add input requirement + OQ for the forbidden-words list | — | open |
| CGAP-002 | blocker | R2.verbatim-vs-paraphrase | decomposition/testability | FW L13 distinguishes must-say-a-specific-way phrases; FR-4.2 lumps "required phrasings honored" | no acceptance criterion; a planner can't tell exact-match from semantic-match scoring | decompose FR-4.2 into verbatim-required vs semantic elements + criterion | — | open |
| CGAP-003 | blocker | R22.call-type | partial coverage | CS L104 callback script; FR-4.1 (L145-146) omits call type | callback calls scored against wrong element set | add call-type (first-contact vs callback) to FR-4.1 classification | — | open |
| CGAP-004 | blocker | R12.correct-values | omission | FW L5 individualized offers; CS full of per-client placeholders (price/channels/Mbps) | scoring "said the element" ≠ "said the right numbers"; no per-client offer-data input | add explicit decision: score structure now, value-correctness needs per-client offer data (input req + OQ) | — | open |
| CGAP-005 | blocker | R25.redaction-recall | NFR omission (safety) | compliance-first (this session); CS L32 EGN | without a recall-bias requirement, a missed EGN slips through — the exact failure the client fears | add NFR: redaction favors recall/over-redaction; residual-PII target | — | open |
| CGAP-006 | blocker | R11.data-entry-eval | scope-boundary explicitness | FW L19; §5 "candidate cross-checks" | silently undecided — not addressed, not scoped out | explicitly scope data-entry evaluation OUT of first slice (first slice = L23 focus) with rationale | — | open |
| CGAP-007 | blocker | R30.non-conversation | negative/boundary | auto-dialer FW L5 yields no-answer/voicemail/aborted calls | pipeline would try to score a non-dialogue or fabricate a result | add boundary requirement: detect + skip/flag non-conversation calls pre-eval | — | open |

### Cleanup List

| item_id | req | issue | optional fix |
| --- | --- | --- | --- |
| CC1 | R8 | outcome taxonomy undefined | fold into OQ-5 (client system provides outcome set) |
| CC2 | R10 | per-pattern acceptance criteria are coarse | defer detailed criteria to plan |

## Cycle 1 Plan

### Gap-To-Fix Map

| gap_id | target section | exact addition | validation |
| --- | --- | --- | --- |
| CGAP-001 | §7 S2 or new input req + §10 OQ-9 | forbidden-words list is a required client-provided config input | grep "forbidden-words list" present as input + OQ |
| CGAP-002 | §7 FR-4.2 | split into verbatim-required (exact/near-exact match) vs conveyed-content (semantic match) with criterion | re-read FR-4.2 |
| CGAP-003 | §7 FR-4.1 | add "call type: first-contact vs repeat/decision callback (CS L104)" | re-read FR-4.1 |
| CGAP-004 | §3 or §7 FR-4.2 | lock: first slice scores element presence/structure; value-correctness requires per-client offer data → OQ-10 | re-read; grep OQ-10 |
| CGAP-005 | §8 new NFR-6 | redaction biases toward recall/over-redaction; residual-PII is safety-critical | grep NFR-6 |
| CGAP-006 | §7 or §11 | explicit out-of-scope: data-entry-accuracy evaluation not in first slice (L23 focus), candidate for later W | grep "out of scope" data entry |
| CGAP-007 | §4 or §7 S1 | boundary req: classify + skip/flag non-conversation recordings before S2/S4 | re-read S1 |

## Cycle 1 Edits

- CGAP-001: added FR-1.3 (forbidden-words list as client-provided input) + OQ-9.
- CGAP-002: FR-4.2 split into verbatim-required (exact/near-exact) vs conveyed-content (semantic) match modes; verbatim tagging → rubric authoring (§6).
- CGAP-003: FR-4.1 adds call-type (first-contact vs callback, CS L104).
- CGAP-004: new locked decision §3.6 (score structure now; value-correctness needs per-client offer data) + FR-1.3 + OQ-10.
- CGAP-005: new NFR-6 (redaction biases toward recall/over-redaction; residual-PII target OQ-6).
- CGAP-006: §5 explicit out-of-scope for data-entry-accuracy evaluation (first slice = L23 focus; later W4).
- CGAP-007: FR-1.2 non-conversation detection + skip/flag before S2/S4.

## Cycle 1 Validation

- `grep` confirms FR-1.2, FR-1.3, FR-4.1 call-type, FR-4.2 match-modes, §3.6, NFR-6, OQ-9, OQ-10, §5 out-of-scope all present.
- §3 renumbered 1–7 cleanly; `§3.6` reference in OQ-10 resolves to the structure-vs-value decision (correct).
- `git diff --check` exit 0.

### Post-Edit New-Gap Pass (Cycle 1)

| changed unit | checked against | result | new gap id |
| --- | --- | --- | --- |
| NFR-6 (over-redaction) | R1 / FR-4.2 (adherence scoring) | **conflict** — over-masked benign audio would be misread as an agent miss | **CGAP-008** |
| FR-1.3 inputs | OQ-9/OQ-10 | tied to explicit OQs; no orphan | none |
| §3.6 value-deferral | FR-4.2 | consistent (FR-4.2 scores presence/structure) | none |
| FR-1.2 non-conversation | §4 pipeline | consistent; runs before S2 | none |

## Cycle 2 Assessment

Fresh full pass. Prior CGAP-001..007: **closed** (mechanisms verified above). One **new** blocker from the post-edit pass:

| gap_id | severity | req.obligation | lens | evidence | why uncovered | planned fix | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CGAP-008 | blocker | R24×R1 conflict | conflict/reconciliation | NFR-6 over-redaction (L204-207) vs FR-4.2 adherence scoring | masked benign span scored as agent miss → false negatives; conflict unreconciled | S2 emits a redaction map (timestamps+category, no values); FR-4.2 treats masked spans as indeterminate | open |

## Cycle 2 Plan

| gap_id | target | edit | validation |
| --- | --- | --- | --- |
| CGAP-008 | §7 S2 + FR-4.2 | add FR-2.4 redaction map; FR-4.2 treats FR-2.4-flagged spans as indeterminate not misses | re-read FR-2.4 + FR-4.2 |

## Cycle 2 Edits

- CGAP-008: added FR-2.4 (redaction map: timestamps + PII category, no PII values, consumed by S3/S4); FR-4.2 now treats masked spans as **indeterminate**, not agent misses.

## Cycle 2 Validation

- FR-2.4 present; FR-4.2 "indeterminate" clause present.
- Post-edit new-gap pass: FR-2.4 emits no PII values (compliance-consistent); "indeterminate" scoring policy is a plan-level detail, acceptable at requirements altitude; no new conflict introduced.

## Cycle 3 Assessment (fresh full pass, no edits)

Re-traced the full requirement set R1–R31. Every obligation addressed or explicitly scoped-out:

- R2.forbidden-words → FR-1.3+OQ-9; R2.verbatim → FR-4.2 match modes.
- R11 → explicit out-of-scope (§5, W4). R12 → §3.6 deferred + OQ-10. R22 → FR-4.1 call-type.
- R25 → NFR-6; reconciled with R1 via FR-2.4 (CGAP-008 closed). R30 → FR-1.2.
- R5 → out-of-scope-later (§11 W5). All CallScript rubric elements R13–R21 → §6.1-6.9.

Blocker coverage gaps this pass: **0**. CGAP-001..008: **closed**.

## Final Convergence Check

No-edit cycle (Cycle 3). Fresh full pass over the complete requirement set found zero blocker coverage gaps.

### Final Coverage Proof

| req_id | every obligation covered or scoped-out? | acceptance criterion present? | evidence |
| --- | --- | --- | --- |
| R1-R3 | yes | yes (element said/order/match-mode) | §5, §6, FR-4.1/4.2 |
| R4-R6 | yes | yes (prosody + turn-pairing) | §3.4, FR-3', FR-4.4/4.5 |
| R7-R10 | yes | yes (duration/result/pattern flags) | FR-4.6/4.7 |
| R11 | scoped-out (first slice) w/ rationale | n/a | §5, §11 W4 |
| R12 | deferred w/ rationale + input path | yes (structure now; value on OQ-10) | §3.6, FR-1.3 |
| R13-R21 | yes | yes (branch-selected mandatory set) | §6, FR-4.1 |
| R22 | yes | yes (call-type classification) | FR-4.1 |
| R23-R24 | yes | yes (Bulgarian STT; redaction gate) | NFR-1, §4, FR-2.x |
| R25 | yes, reconciled | yes (recall bias; residual-PII OQ-6) | NFR-6, FR-2.4 |
| R26-R29,R31 | yes | yes | NFR-3/4/5, FR-X.1, FR-4.7 |
| R30 | yes | yes (skip/flag non-conversation) | FR-1.2 |

### Convergence Statement

Converged after **2 fix cycles + 1 clean pass**. Convergence means **breadth** only — every elicited
requirement is addressed or explicitly scoped-out with a testable criterion. It does **not** establish
that each addressed requirement actually holds end-to-end. Requirements intentionally excluded from the
first slice: customer-emotion (R5), data-entry-accuracy evaluation (R11), value-correctness scoring
(R12, deferred pending OQ-10) — each recorded with rationale. Next: gate 3
`requirements-satisfaction-gap-loop` (depth).
