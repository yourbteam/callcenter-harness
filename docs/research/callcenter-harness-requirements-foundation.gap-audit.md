# Gap Audit — callcenter-harness-requirements-foundation.md

Loop: `doc-gap-closure-loop` (internal-readiness gate 1 of 3). Target:
`callcenter-harness-requirements-foundation.md` (267 lines). Scope: internal document readiness
only (self-sufficient, internally consistent, cited claims real). Does **not** establish interop,
runtime/data reality, or end-to-end requirement satisfaction — those are the coverage/satisfaction gates.

## Cycle 1 Assessment

### Section Inventory

| unit_id | section/title | unit type | implementation relevance |
| --- | --- | --- | --- |
| U1 | Intro + Status blockquote (L3-8) | intro text | frames mode/status; status claim must match §10/§12 |
| U2 | §1 Purpose (L10-15) | heading section | scope of the harness |
| U3 | §2 Sources table (L17-23) | table | provenance of every claim |
| U4 | §3 Locked decisions (L25-40) | locked-decision list | the binding decisions a planner must not re-open |
| U5 | §4 Processing pipeline + note (L42-62) | diagram + claim | the stage backbone |
| U6 | §5 What the harness evaluates (L64-82) | list | evaluation dimensions + source citations |
| U7 | §6 Script-derived rubric (L84-112) | numbered list | the rubric content + CallScript citations |
| U8 | §6 Design implication (L114-117) | claim block | branch-dependent scoring |
| U9 | §7 Functional requirements (L119-166) | field/req list | per-stage FRs |
| U10 | §8 Non-functional requirements (L168-180) | list | NFRs |
| U11 | §9 Harness-base recommendation (L182-224) | claim block | UP-reuse decision + UP source citations |
| U12 | §10 Open questions (L226-244) | list | resolved/deferred OQs |
| U13 | §11 Workflows decomposition (L246-257) | list | W1-W5 mapping + L15 citation |
| U14 | §12 Next steps (L259-267) | list | handoff to gates/plan |

### Coverage Matrix

| unit_id | lens | status | evidence |
| --- | --- | --- | --- |
| U1 | contradictions | gap found | GAP-003: L8 "open questions must be resolved before planning" contradicts §10/§12 which mark OQ-1-3 resolved, OQ-4-8 non-blocking |
| U2 | decision completeness | checked | scope (audio-in, per-call eval) is concrete (L12-15) |
| U3 | repo grounding | checked | 3 sources exist: `ClientFiles/FirstWorkflow.md`, `ClientFiles/CallScript.docx`, `../united-partners` all verified present this session |
| U4 | contradictions | gap found | GAP-004: §3.2 pipeline says "evaluate performance from the transcript" (L30) but §3.4/§4/FR-4.4 route prosody features into the evaluator too |
| U4 | decision completeness | checked | 6 locked decisions each concrete |
| U5 | data flow | checked | S1→S2→(S3‖S3')→S4 diagram consistent with FR set (L44-58) |
| U6 | repo grounding | gap found | GAP-001: L69 & L74 cite `FirstWorkflow L16` for script-adherence + active-listening; L16 is a **blank line**. Content is on L23 |
| U6 | repo grounding | checked | L9/L11/L13/L15/L17/L19 citations verified against FirstWorkflow.md content |
| U7 | repo grounding | checked | CallScript L1-L3/L4/L5-L7/L8/L18/L25-L27/L29/L32/L36-L40/L45-L112/L87-L98/L116-L202/L119/L128-L131/L139 all verified against source; L20-L22 router range includes L22 (headphones) — minor, cleanup C1 |
| U8 | decision completeness | checked | branch-dependent scoring stated; classification requirement lands in FR-4.1 |
| U9 | schema/field semantics | checked | FRs reference OQ-4/OQ-5 for deferred detail; bounded by §12 |
| U9 | vague wording | gap found (cleanup) | C2: FR-1.1 "format/codec TBD" — acceptable at requirements altitude but bare "TBD" should name the deferral |
| U10 | decision completeness | checked | NFR-1..5 each concrete; defer targets to OQ-6/OQ-7 explicitly |
| U11 | repo grounding | checked | UP citations verified this session: `runner.py:83-114` elif chain; `runner.py:147-160` phase_ledger; `runner.py:130-145` ingestion; `runner.py:426-433` text-only sources; `state/store.py:23` `output: str` |
| U12 | contradictions | gap found | GAP-003 (same as U1): §10 header "(must resolve before planning)" now stale — all are resolved or deferred |
| U13 | repo grounding | gap found | GAP-002: L246 heading cites `client's framing, L15`; the "several interconnected workflows" phrase is on **L23**, not L15 |
| U14 | contradictions | gap found (cleanup) | C3: L264 "if you want, run the three gates... I will not launch without your go" is stale — hardening is now default and this gate is running |

### Blocker Gap Ledger

| gap_id | severity | unit_id | lens | evidence | why blocker | planned fix | closure evidence | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-001 | blocker | U6 | repo grounding | doc L69 `(FirstWorkflow L7, L13, L15, L16.)` and L74 `(L16, closing)`; `FirstWorkflow.md` L16 is blank, content on L23 | a planner verifying provenance follows L16 → blank line → must re-derive; ungrounded citation | change L16→L23 in both places; cite the L23 phrase | — | open |
| GAP-002 | blocker | U13 | repo grounding | doc L246 `(client's framing, L15)`; "няколко уъркфлоа реално свързани" is `FirstWorkflow.md` L23, L15 is the monitoring sentence | wrong provenance for the whole §11 decomposition premise | change L15→L23 in the §11 heading | — | open |
| GAP-003 | blocker | U1,U12 | contradictions | doc L8 "Open questions in §10 must be resolved before this becomes a plan" vs L232-235 (OQ-3 resolved) and L261-263 (OQ-4-8 non-blocking) | a planner reads L8 as "blocked", contradicting §12; forces reconciliation | rewrite L8 status to reflect resolved/deferred state; soften §10 header | — | open |
| GAP-004 | blocker | U4 | contradictions | doc L28-30 locked decision "evaluate performance from the transcript" vs L33-35 (prosody path), L56-57 (S4 = transcript+prosody), L153-156 (FR-4.4/4.5 use prosody) | contradictory LOCKED decision: is prosody an evaluator input or not? planner building S4 can't tell | amend §3.2 to "transcript + parallel prosody features" | — | open |

### Cleanup List

| item_id | unit_id | issue | optional fix |
| --- | --- | --- | --- |
| C1 | U7 | §6.2 "router options *(L20–L22)*" — L22 is the headphones line, not router | narrow to L20-L21 |
| C2 | U9 | FR-1.1 bare "TBD" | reword to "to confirm with client in planning (OQ-4)" |
| C3 | U14 | §12 "if you want... I will not launch without your go" stale vs always-harden | reword to reflect hardening in progress |
| C4 | U6 | L72 agent emotion cites "(L9, L11)"; L11 is customer emotion | narrow agent-emotion cite to L9 |

## Cycle 1 Plan

### Gap-To-Fix Map

| gap_id | target unit | exact decision to lock | edit summary | validation check |
| --- | --- | --- | --- | --- |
| GAP-001 | U6 (L69, L74) | active-listening/adherence provenance is FirstWorkflow L23 | replace `L16` with `L23`; L74 cite the "активнослушане" phrase | grep no `L16` remains as a FirstWorkflow cite |
| GAP-002 | U13 (L246) | "several workflows" provenance is L23 | replace `L15` with `L23` in heading | grep §11 heading shows L23 |
| GAP-003 | U1 (L8), U12 (L226) | status = OQ-1-3 resolved, OQ-4-8 deferred to planning | rewrite status line; soften §10 header to "(status)" | re-read L8 + §10 header consistent with §12 |
| GAP-004 | U4 (L28-30) | evaluator consumes transcript AND prosody | append "+ parallel prosody features (§3.4)" to the pipeline decision | re-read §3.2 vs FR-4.4 — no contradiction |
| C1-C4 | U6,U7,U9,U14 | (cleanup) | narrow L20-L21; reword TBD; reword §12; narrow L9 cite | grep TBD; re-read |

## Cycle 1 Edits

- GAP-001: §5 — `FirstWorkflow L16`→`L23` (adherence line); active-listening cite → `L23`; agent-emotion cite narrowed `(L9, L11)`→`(L9)`.
- GAP-002: §11 heading — `client's framing, L15`→`L23`.
- GAP-003: Status blockquote rewritten to "OQ-1–OQ-3 resolved; OQ-4–OQ-8 operational"; §10 header `(must resolve before planning)`→`(status)`.
- GAP-004: §3.2 locked decision — appended "plus the parallel prosody features (§3.4, §4)".
- C1: §6.2 router range `L20–L22`→`L20–L21`.
- C2: FR-1.1 `format/codec TBD`→`to confirm with client during planning`.
- C3: §12 stale "if you want... I will not launch" → "Hardening (default for build-bound research)... Gate 1 applied; gates 2–3 follow".
- C4: folded into GAP-001 edit (agent-emotion cite narrowed to L9).

## Cycle 1 Validation

Commands run:

- `grep -nE 'TBD|TODO|maybe|could|should|candidate|not locked|needs further|or equivalent'` → hits at L6 (descriptive "should pass gates"), L80 ("candidate cross-checks" — tied to OQ-5, intentional tentativeness), L110 ("agent should use" — describes script content), L180 ("should process… batch" — NFR phrasing). None hide an implementation decision the doc should make. No `TBD`/`TODO`/`not locked` remain.
- `grep -nE 'L16|framing, L15'` → sole hit L97 `L9–L16` is a CallScript upsell range (correct), not a FirstWorkflow cite. No stray blank-line citations.
- `git diff --check` → clean (untracked file; no whitespace errors).

### Post-Edit New-Gap Pass

| changed unit | checked against | result | new gap id |
| --- | --- | --- | --- |
| Status (L8) | §10, §12 | consistent — resolved/deferred framing matches | none |
| §3.2 (L28-31) | FR-4.4/4.5, §4 diagram | consistent — prosody now named as evaluator input everywhere | none |
| §5 (L68-75) | FirstWorkflow.md L9/L13/L15/L23 | citations now land on real content lines | none |
| §11 heading | FirstWorkflow.md L23 | correct provenance | none |
| §12 | actual loop state (gate 1 running) | accurate; no over-claim of gates 2–3 | none |

## Cycle 2 Assessment (fresh full-document pass, no edits)

Re-ran all lenses over U1–U14 on the edited document.

| unit_id | lens | status | evidence |
| --- | --- | --- | --- |
| U1 | contradictions | checked | Status now aligns with §10/§12 |
| U2 | decision completeness | checked | scope concrete |
| U3 | repo grounding | checked | 3 sources present |
| U4 | contradictions / completeness | checked | §3.2 now lists prosody as evaluator input; 6 decisions concrete, non-contradicting |
| U5 | data flow | checked | diagram matches FR set |
| U6 | repo grounding | checked | L9/L13/L15/L23 cites verified against FirstWorkflow.md |
| U7 | repo grounding | checked | CallScript cites verified; router range corrected |
| U8 | decision completeness | checked | branch-dependent scoring → FR-4.1 |
| U9 | schema/vague wording | checked | deferred detail bounded to OQ-4/OQ-5; no bare TBD |
| U10 | decision completeness | checked | NFR-1..5 concrete |
| U11 | repo grounding | checked | UP citations verified this session |
| U12 | contradictions | checked | header softened; content resolved/deferred |
| U13 | repo grounding | checked | L23 provenance correct |
| U14 | contradictions | checked | reflects always-harden + current gate state |

Blocker gaps found this pass: **0**. Prior gaps GAP-001..GAP-004: **closed**. Cleanups C1–C4: **closed**.

## Final Convergence Check

This is a no-edit cycle (Cycle 2 made no document edits). Fresh full-document pass found zero blocker gaps.

### Final Readiness Proof (internal readiness only)

| category | status | evidence |
| --- | --- | --- |
| runtime entry points / data flow | ready | §4 pipeline S1→S2→(S3‖S3')→S4; consistent with FRs |
| schema/fields/interfaces | ready (requirements altitude) | FR set + UP reuse mapping §9; concrete field detail explicitly deferred to plan via OQ-4/OQ-5 |
| edge cases / failure behavior | ready | S2 redaction gate (FR-2.3); NFR-4 low-confidence handling |
| resume/idempotency | n/a at requirements altitude | this is a requirements foundation, not an implementation plan; idempotency is a plan-stage concern |
| validation / acceptance | ready | per-call QA report FR-4.7; NFR-5 auditability maps to UP `exact_source_quote_coverage` |
| repo grounding | ready | all FirstWorkflow/CallScript/UP citations verified this session |
| approval boundaries | ready | harness-base decision recorded (§9); no un-owned approval gate |
| out-of-scope boundaries | ready | OQ-4-8 deferred; W4/W5 marked later (§11); customer emotion later |

### Convergence Statement

Converged after **1 fix cycle + 1 clean pass**. Convergence means **internal document readiness only** —
the document is self-sufficient, internally consistent, and its cited claims are real. It does **not**
establish interop, runtime/data reality, or end-to-end requirement satisfaction. Next: gate 2
`requirements-coverage-gap-loop` (breadth), then gate 3 `requirements-satisfaction-gap-loop` (depth).
