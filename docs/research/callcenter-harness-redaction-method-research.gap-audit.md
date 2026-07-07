# Gap Audit — callcenter-harness-redaction-method-research.md

Loop: `doc-gap-closure-loop` (internal-readiness gate 1 of 3). Scope: self-sufficient, consistent,
cited claims real. Not interop/runtime/end-to-end (later gates).

## Cycle 1 Assessment

### Section Inventory

| unit_id | section/title | unit type | implementation relevance |
| --- | --- | --- | --- |
| U1 | Intro blockquote (L3-5) | intro | constraints framing |
| U2 | §1 Approach (L7-17) | section | chosen vs rejected approach |
| U3 | §2 PII taxonomy table (L19-30) | table | per-type detection |
| U4 | §3 Tooling recommendation (L32-46) | section | Presidio + masking mechanism |
| U5 | §4 BG NER options (L48-63) | section | the weak link |
| U6 | §5 Two hard problems (L65-82) | section | spoken numbers + weak NER |
| U7 | §6 Recall-first design (L84-95) | section | NFR-6 mechanisms |
| U8 | §7 Dual-channel (L97-102) | section | per-channel detection |
| U9 | §8 Measurement (L104-112) | section | recall measurement + blocker |
| U10 | §9 Architecture diagram (L114-129) | diagram | S2 internals |
| U11 | §10 Open questions (L131-139) | list | OQs |
| U12 | §11 Sources (L141-...) | list | citations |

### Coverage Matrix (key lenses)

| unit_id | lens | status | evidence |
| --- | --- | --- | --- |
| U3 | schema/helper semantics | gap found | GAP-001: char span → word token → audio time mapping never specified (also U4 L47, U10 diagram) |
| U3 | repo grounding | checked | EGN weights `[2,4,8,5,10,9,7,3,6]` mod 11 cited [3]; verified in search |
| U4 | data flow | gap found | GAP-001 (same): Presidio returns char offsets; how they resolve to words.json word ts is unstated |
| U4 | API semantics | gap found | GAP-003: Presidio needs an explicit `language="bg"` NLP-engine backend; no spaCy bg model exists — which backend is unlocked |
| U5 | repo grounding | checked | iarfmoose/roberta-small-bulgarian-ner, WikiANN-bg cited [4] |
| U6 | decision completeness | gap found | GAP-002: "Bulgarian number-word normalizer" (L92) named but undefined — library or custom? un-sourced |
| U6 | repo grounding | checked | Whisper digits-by-default + digit-align gap cited [5] |
| U7 | data-reality | checked | words.json has both segment and word start/end (verified this session) — segment fallback is real |
| U9 | end-to-end trace | checked | diagram consistent with FR-2.4/FR-2.3/NFR-6/§3.5 (requirements doc) |
| U11 | contradictions | checked | OQ-6 consistent with requirements-foundation OQ-6 |
| U12 | repo grounding | checked | all 5 source URLs are the pages fetched/searched this session |

### Blocker Gap Ledger

| gap_id | severity | unit_id | lens | evidence | why blocker | planned fix | closure evidence | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-001 | blocker | U3/U4/U10 | data flow | doc L47 "map spans → words → audio time"; L114-129 diagram — no mechanism for aligning Presidio char offsets to words.json tokens | the core of S2 (detect→mask) can't be built without the span→time mapping | add mechanism: assemble analyzer text by joining word tokens, keep a char-offset→word-index map so Presidio spans resolve to word start/end | — | open |
| GAP-002 | blocker | U6 | decision completeness | doc L92 "Bulgarian number-word normalizer" — undefined, un-sourced | planner can't tell if it's a dependency or build work | mark as a **custom** small BG number-word→digit map (inference); build work, not a library | — | open |
| GAP-003 | blocker | U4/U5 | API semantics | doc §3/§4 imply a bg NLP engine but never lock which; spaCy has no bg pipeline | planner needs the concrete Presidio bg backend | lock: Presidio bg uses the **transformers NlpEngine** (BG NER model) or Stanza `bg`; spaCy bg is not available | — | open |

### Cleanup List

| item_id | unit_id | issue | optional fix |
| --- | --- | --- | --- |
| CC1 | U4 | ffmpeg `volume=enable=between(...)` shown for one range; many ranges need OR'd enable or chained filters | note the many-range form |

## Cycle 1 Plan

### Gap-To-Fix Map

| gap_id | target | edit | validation |
| --- | --- | --- | --- |
| GAP-001 | §3 + §9 | add the char-offset→word-index→audio-time mapping mechanism | grep "char-offset" / "word-index" present |
| GAP-002 | §5 | mark number-word normalizer as custom (inference) | re-read L92 |
| GAP-003 | §3/§4 | lock Presidio bg NLP-engine backend (transformers/Stanza; not spaCy) | grep "transformers NlpEngine"/"Stanza" |
| CC1 | §3 | note many-range ffmpeg form | re-read |

## Cycle 1 Edits

- GAP-001: §3 — added the char-offset→word-index map (join `words.json` tokens; resolve Presidio spans to word `start/end`); §3 masking now names many-range ffmpeg form.
- GAP-002: §5(b) — number-word normalizer marked **custom / inference / build work**, not a library.
- GAP-003: §3 — Presidio `bg` NLP engine locked to transformers `NlpEngine` (BG NER) or Stanza `bg`, not spaCy; invoked `language="bg"`.
- CC1: folded into GAP-001 masking edit.

## Cycle 1 Validation

- `grep` confirms `char-offset → word-index map`, `transformers NlpEngine`, `custom Bulgarian number-word`, many-range `between(t,t3,t4)` all present.
- Unresolved-term scan: none. `git diff --check` exit 0.

### Post-Edit New-Gap Pass

| changed unit | checked against | result | new gap id |
| --- | --- | --- | --- |
| §3 char map | Presidio char-offset semantics | offsets are into OUR joined text → map holds regardless of Presidio internal tokenization | none |
| §3 bg backend | §4 model list | transformers NlpEngine consumes a §4 BG NER model — consistent | none |
| §5 normalizer | §6 catch-all recognizer | normalizer is belt-and-suspenders; catch-all still fires without it | none |

## Cycle 2 Assessment (fresh full pass, no edits)

Re-ran all lenses over U1–U12. GAP-001/002/003 closed (mechanisms now concrete). Cited claims (EGN
weights [3], BG NER models [4], Whisper digit behavior [5], Presidio [1], GLiNER [2]) all verified this
session. No contradictions with the requirements foundation (FR-2.3/2.4, NFR-6/7, §3.5, OQ-6). Blocker
gaps this pass: **0**.

## Final Convergence Check

No-edit cycle. Fresh full pass found zero blocker gaps.

### Final Readiness Proof

| category | status | evidence |
| --- | --- | --- |
| data flow / entry points | ready | §9 diagram; §3 span→time map |
| schema/interfaces | ready | words.json (segment+word ts) → Presidio spans → ffmpeg ranges; redaction map shape given |
| edge cases / failure | ready | spoken-number + weak-NER hazards + mitigations (§5); hold-on-low-confidence (§6) |
| validation / acceptance | ready (with caveat) | recall test needs a labeled set (§8, OQ-6) — flagged, not hidden |
| repo grounding | ready | all cited claims verified this session |
| out-of-scope | ready | audio-domain detection rejected (§1); over-mask acceptable per §3.5 |

### Convergence Statement

Converged after **1 fix cycle + 1 clean pass**. Internal-readiness only. Recall measurement depends on a
labeled ground-truth set (OQ-6) — an explicit external dependency, not an internal gap. Next: gate 2
`requirements-coverage-gap-loop` (breadth), then gate 3 `requirements-satisfaction-gap-loop` (depth).
