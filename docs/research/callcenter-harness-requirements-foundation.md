# Call-Center Harness — Requirements Foundation (Research)

> **Mode:** Research (research-playbook). This document gathers and structures what the two
> client files establish, maps it onto a harness design, and turns it into a first requirement
> set. It is **build-bound** — it is meant to feed an implementation — so before anything is
> built on it, it should pass the three hardening gates (see §12).
>
> **Status:** Draft foundation. All planning-blocker open questions (OQ-1–OQ-3) are resolved; the
> remaining ones (OQ-4–OQ-8) are operational details to settle during the planning stage (see §10, §12).

## 1. Purpose

Define the requirements for a new **call-center QA harness** for the client (an A1 Bulgaria
outbound tele-sales operation). The harness ingests recorded sales calls and produces a
**per-call performance evaluation** against the client's mandatory script, so team leaders can
see whether an agent followed the script, how they sounded, and where calls break.

## 2. Sources

| Source | What it gives us |
| --- | --- |
| `ClientFiles/FirstWorkflow.md` | The client's own description of the operation, what they monitor, agent failure patterns, and the explicit first-workflow scope. |
| `ClientFiles/CallScript.docx` | The gold-standard A1 sales script — the compliance rubric the harness scores against (opening, offers 1–3, cross-sell rules, objection bank, 5 legal-part variants, mandatory closing). |
| `../united-partners` harness (reference) | An existing Python MCP-stdio workflow harness (YAML phases; producer/verifier/critic phase-ledger scoring loop; gates; feedback/rerun; artifact export). Referenced for **harness operation**, per the request. |

## 3. Locked decisions (from scoping)

1. **Input is audio recordings.** The harness owns speech-to-text; it is not handed transcripts.
2. **Processing pipeline (client-specified):**
   `raw audio recording → GDPR-redact the recording (produce a compliant recording) → transcribe
   the compliant recording → evaluate performance from the transcript plus the parallel prosody
   features (§3.4, §4)`.
3. **First slice covers all three evaluation dimensions:** (1) script adherence, (2) intonation &
   emotion, (3) active listening.
4. **Intonation/emotion source (resolves OQ-1):** a **parallel prosody path** extracts acoustic
   features (pitch, pace, energy, pauses) from the **compliant recording** and feeds them into the
   evaluator alongside the transcript. Emotion is not inferred from text alone.
5. **Compliance-first scoring (resolves OQ-2):** mandatory script elements whose **content is the
   removed PII** (e.g. the agent stating the customer's name/address in the opening) are **not scored
   for now** — we do not reconstruct redacted data to grade it. Adherence scoring covers the non-PII
   elements (offer content, upsell, order, objection rebuttals, forbidden words, legal disclosures).
6. **Structure vs value scoring (first slice):** adherence scores element **presence, structure, and
   order**. Verifying the agent quoted the **correct individualized values** (price/channels/Mbps —
   offers are per-client, *FirstWorkflow L5*) requires per-client offer data (FR-1.3, OQ-10) and is
   **deferred** until that data is available.
7. **Harness base:** recommendation requested — see §9.

## 4. Processing pipeline (the backbone)

```
[S1] Ingest raw call recording
       │
[S2] GDPR redaction on audio  ─────►  compliant recording (PII removed/masked)
       │
       ├──────────────────────────────────────────────┐
       │                                               │
[S3] Transcription (Bulgarian STT,            [S3'] Prosody feature extraction
     speaker-diarized: agent vs. customer)         (pitch, pace, energy, pauses)
       │                                               │
       └───────────────────────┬───────────────────────┘
                               │
[S4] Performance evaluation  ─────►  per-call QA report + scores
     (transcript + prosody features)
```

Each stage is a natural harness **phase**. S2 is a hard gate: **no transcript, prosody path, or
evaluation may be produced from un-redacted audio** (compliance requirement, §8). Both S3 (transcript)
and S3' (prosody) run off the **compliant recording** and converge at S4.

**Note on S2 internals (redaction is transcript-driven):** to *locate* PII, S2 transcribes the raw audio
**ephemerally inside the air-gap** (that transcript is used only for detection and immediately discarded —
never persisted or passed downstream), masks the audio, and emits the compliant recording. The
**evaluation** transcript (S3) is then produced from that **compliant** recording, so it is PII-free by
construction. See the redaction-method research + first-slice plan §0.6.

## 5. What the harness evaluates

Grounded in `FirstWorkflow.md`:

- **Script adherence** — did the agent say the mandatory elements, in the mandatory way, in the
  mandatory order? *(FirstWorkflow L7, L13, L15, L23.)* Specifically: start from **Offer 1**, rebut
  objections, and only then move to the next offer *(L9)*; use required phrasings and avoid
  forbidden words *(L13)*.
- **Intonation & emotion** — confidence, smile, emotion, clear diction *(L9)*; ideally also the
  **customer's** emotion *(L11, marked "later")*.
- **Active listening** — did the agent respond to what the customer actually said *(L23 — the
  first-slice focus lists "активнослушане")*.
- **Outcome & operational metrics** — call **duration**, **result/outcome**, adherence to mandatory
  elements *(L15)*; post-call the agent enters **order, address, comment, result** into the system
  *(L19)*. **Out of scope for the first slice:** evaluating the *accuracy* of those agent data entries —
  the first slice scores script adherence, intonation/emotion, and active listening *(L23)*, not
  data-entry correctness. That becomes a later workflow (§11 W4) and depends on OQ-5.
- **Break-point / template detection** — team leaders want to know whether there is a **template that
  makes an agent successful**, or a **specific point where calls break** *(L15)*. Named failure
  patterns to detect *(L17)*: sluggish delivery; losing the customer in the first seconds; giving up
  early; not repeating/praising the offer; not stating practical benefits; not asking for the
  decision (sometimes repeatedly).

## 6. The script-derived rubric (evaluation source of truth)

`CallScript.docx` decomposes into a scorable structure. This is the raw material for the S4 phase
contract:

1. **Opening & identification** — greet, name A1, ask for Mr/Mrs X; handle "not convenient"; **record-
   consent disclosure** *(L1–L3)*.
2. **Offer 1** — address reference (settlement only) *(L4)*; discount + **device bonus** (Huawei
   FreeBuds SE 4 / Band 11) *(L5–L7)*; current-plan recap *(L8)*; double/triple-pack upsell — speed,
   channels, HD, MAX Sport, select packages (Netflix/HBO MAX/Cinemax/SkyShowtime/VOYO/Diema
   Xtra/Storytel) *(L9–L16)*; price framing (12 + 12 months, online-payment discount) *(L18)*;
   receiver discounts *(L19)*; router options *(L20–L21)*; e-sign / courier logistics *(L24)*.
3. **Cross-sell decision rule (hard branch)** — on an accepted re-sign, **before the legal part,
   mandatorily check the card for MBB / Netbox on the EGN** *(L32)*: if no MBB → offer **data card**
   *(L36–L37)*; if MBB but no Netbox → offer **Netbox 25 GB** *(L39–L40)*.
4. **Offer escalation ladder** — **Offer 2** (new tariff plan / reset with router 1.02€) *(L25–L26)*;
   **Offer 3** (reset — retain conditions 24 months) *(L27)*.
5. **Mandatory post-acceptance questions** — headphones? router? *(L29)*.
6. **Objection-handling bank (~15 types, each with prescribed rebuttal)** *(L45–L112)* — not
   interested / happy as is; want to think / ask family; don't watch TV; don't need internet/speed;
   when does my contract expire; I'll wait for expiry; I'll visit a store; too expensive; don't want
   to talk; long contract term; technical complaints; speed complaints; decline router retention;
   cross-sell "already have it" objection.
7. **"Cents-per-day" reframing table** *(L87–L98)* — a specific rhetorical device the agent should use.
8. **Legal part — 5 variants** *(L116–L202)*: new plan (e-sign); reset (e-sign); new plan w/ device
   (courier); reset w/ device (courier); re-sign + new service (courier). Each carries mandatory
   disclosures: **14-day withdrawal**, **3.07€ remote-delivery fee**, personal-signing-only, GDPR
   consent form, billing explanation, Xplore TV GO MAX.
9. **Mandatory closing** — recap of accepted offer + "anything else?" + thank-you *(L128–L131)*.

**Design implication:** the rubric is **branch-dependent** — which mandatory elements apply depends
on the path taken (which offer accepted, e-sign vs courier, device vs no device, cross-sell branch).
The evaluator cannot use a single flat checklist; it must first **classify the call path**, then score
the mandatory elements **for that path** by selecting the matching **per-branch contract** — a single
static contract's per-category minimums would false-fail legitimately-absent branch elements (§9,
`manager.py:188-202`).

## 7. Functional requirements (per stage)

**S1 — Ingest**
- FR-1.1 Accept call recordings (format/codec to confirm with client during planning — OQ-4) and
  per-call metadata (agent ID, timestamp, campaign, and the agent's post-call entries:
  order/address/comment/result — OQ-5).
- FR-1.2 **Non-conversation handling** — the auto-dialer *(FirstWorkflow L5)* produces recordings that
  are not real dialogues (no answer, voicemail, immediate hang-up, sub-threshold duration). Detect and
  **skip/flag** these before S2/S4 rather than producing a fabricated evaluation (min-duration and
  no-answer/voicemail detection thresholds set during planning).
- FR-1.3 **Reference inputs (client-provided config, not derivable from the recording):** the
  **forbidden-words list** (`FirstWorkflow.md` L13 names that forbidden words exist but does not list
  them — OQ-9), and the **per-client offer data** (individualized price/channels/Mbps) needed for
  value-correctness scoring (OQ-10).

**S2 — GDPR redaction (audio → compliant recording)**
- FR-2.1 Detect and remove/mask personal data spoken in the call. Target PII, evidenced by the script:
  **customer name** *(L1, L3)*, **address / location** *(L4, L19)*, **EGN** *(L32)*, **mobile/phone
  number** *(L119, L139)*, and any payment identifiers.
- FR-2.2 Output a **compliant recording** that is the only artifact allowed to flow downstream.
- FR-2.3 Redaction is a **gate**: on redaction failure/low confidence, the call is held, not transcribed.
- FR-2.4 **Redaction map** — S2 emits a structured map of redacted spans (timestamps + PII category,
  **no PII values**) that S3/S4 consume. This reconciles NFR-6 (over-redaction) with adherence scoring:
  a masked span is distinguishable from a genuine agent omission, so FR-4.2 does not misread
  over-masked benign audio as a missing script element.

**S3 — Transcription**
- FR-3.1 Bulgarian speech-to-text over the compliant recording.
- FR-3.2 **Speaker diarization** — separate agent turns from customer turns (required for adherence,
  active listening, and objection/rebuttal pairing).
- FR-3.3 Preserve turn timing (for duration and "first seconds" analysis, L17).

**S3' — Prosody feature extraction (parallel path)**
- FR-3'.1 Extract acoustic features from the **compliant recording** — pitch, pace/tempo, energy/volume,
  pauses/silence — per speaker turn, time-aligned with the transcript.
- FR-3'.2 Emit the features as a **text/JSON feature summary** that is the S3' phase output (e.g. per
  turn: `pitch`, `pace`, `energy`, `pause`, plus derived cues). This text form is required so the
  evaluator can quote it — see §9 (the phase-ledger evaluator validates evidence as exact substrings of
  its text source, so numeric features must arrive as quotable text, not as a binary/context file path).
- FR-3'.3 S4 consumes S3' via `input.source: subscribed_phase_outputs` over `subscribes_to: [S3, S3']`,
  so its `source_text` is the transcript **and** the prosody summary; intonation/active-listening items
  then quote exact lines of the prosody summary.
  *(Prosody is derived from audio, not text — this is what keeps dimensions 2–3 in the first slice.)*

**S4 — Performance evaluation (from transcript)**
- FR-4.1 **Call-path classification** — determine **call type** (first-contact vs repeat/decision
  callback, `CallScript.docx` L104), which offer was accepted, e-sign vs courier, device vs none, and
  cross-sell branch — to **select the applicable per-branch contract** (§6 design implication, §9), so
  the evaluator never false-fails on elements that do not apply to this path. A callback is scored
  against the callback contract, not the first-contact opening.
- FR-4.2 **Script-adherence scoring** — for the classified path: mandatory elements said / missed and
  **order** honored (Offer 1 before objection rebuttal before next offer, L9). Two match modes:
  **verbatim-required** phrasings that must be said a specific way *(L13)* are scored by exact/near-exact
  match; **conveyed-content** elements are scored by semantic match. Which phrases are verbatim-required
  is tagged during rubric authoring (§6). **Forbidden words** (from the FR-1.3 list) are flagged on any
  occurrence *(L13)*. **Excludes** mandatory elements whose content is removed PII (per §3.5,
  compliance-first) — those are out of scope for now. Spans flagged in the **FR-2.4 redaction map** are
  treated as **indeterminate**, not as agent misses.
- FR-4.3 **Objection handling** — detect each customer objection and whether the agent gave the
  prescribed rebuttal from the bank *(§6.6)*.
- FR-4.4 **Intonation & emotion** — agent confidence/emotion/diction; customer emotion (later) — scored
  from the **S3' prosody features** combined with transcript turns.
- FR-4.5 **Active listening** — did agent responses track what the customer actually said (transcript
  turn-pairing + prosody cues such as interruptions/pauses from S3').
- FR-4.6 **Break-point / failure-pattern detection** — flag the named patterns in §5 (L17) and locate
  *where* in the call the customer was lost.
- FR-4.7 **Per-call QA report** — scores per dimension, mandatory-element coverage, findings with exact
  transcript quotes, and outcome/duration; reviewable by a team leader.

**Cross-cutting**
- FR-X.1 **Team-leader review loop** — accept reviewer feedback on an evaluation and re-run
  (maps to UP `submit_feedback` / `rerun`).
- FR-X.2 **Aggregate analytics** — across calls/agents: success templates and common break-points
  *(L15)* — likely a later workflow (§11), but the per-call schema must support it.

## 8. Non-functional requirements

- **NFR-1 Language:** Bulgarian throughout (STT, rubric matching, reporting). Script mixes formal
  address and telecom jargon — STT + matching must handle it.
- **NFR-2 Compliance / privacy:** call recordings contain EGN, names, addresses, phone numbers → GDPR.
  Redaction-before-transcription is mandatory (S2 gate); retention, access control, and audit of who
  views evaluations are in scope (details OQ-6).
- **NFR-3 Scale/throughput:** an auto-dialer generates high call volume *(FirstWorkflow L5)*; the
  pipeline should process calls in batch/asynchronously (target volume OQ-7).
- **NFR-4 Accuracy & graceful degradation:** every downstream metric depends on STT quality; the
  harness must expose confidence and never present a low-confidence transcript's score as authoritative.
- **NFR-5 Auditability:** each evaluation traces to exact transcript quotes and to the script element
  it scored (UP's `exact_source_quote_coverage` pattern fits directly).
- **NFR-6 Redaction recall (safety-critical):** because the whole point is compliance, S2 redaction
  **biases toward over-redaction** — a missed EGN/name/phone is a GDPR breach, so recall is prioritized
  over precision even at the cost of over-masking benign audio. The residual-PII tolerance is an
  explicit acceptance target (OQ-6). This is why FR-2.3 holds low-confidence calls rather than passing them.
- **NFR-7 Air-gapped audio processing (no-egress, client requirement 2026-07-07):** every stage that
  touches source or compliant **audio** — redaction (S2), STT (S3), prosody (S3') — must run
  **self-hosted, offline, with no network egress and no telemetry**, so there is **no way for the source
  audio to leak**. Models are **open, self-selected, and vendored** (weights pre-placed, no runtime fetch;
  `HF_HUB_OFFLINE=1`/local-files-only). The guarantee is enforced by **deployment (network-egress-denied
  environment)**, not by trusting a dependency. STT engine decision:
  `callcenter-harness-stt-engine-decision.md` (open Whisper-family, e.g. faster-whisper / whisper.cpp).
  Cloud-SaaS STT (Azure/Google/Deepgram) is **excluded** for the audio path by this requirement.
  Acceptance: a transcription/redaction run **succeeds with outbound network blocked**.

## 9. Harness-base recommendation

**Recommendation: hybrid — build a new audio front-end, reuse the UP harness orchestration spine for
sequencing + evaluation.**

Rationale, grounded in what each side actually does:

- **S1–S3 (ingest, redact, transcribe) are net-new regardless.** The UP harness is a
  text/document workflow orchestrator; it has no audio, STT, diarization, or redaction capability.
  These stages are new services/tools whichever base we pick.
- **S4 (evaluation) maps almost one-to-one onto UP's `phase_ledger_loop`.** The script becomes the
  **phase contract**; a **producer** extracts what the agent said and matches script elements; a
  **verifier** checks mandatory-element coverage, order, and forbidden words; a **critic** catches
  misses. UP's `finding_count`, `category_counts`, and `exact_source_quote_coverage` are already the
  shape of a QA score. Team-leader review = UP `submit_feedback` + `rerun`. The per-call QA report =
  UP `export_artifacts`.
- **UP's YAML phase model** can sequence the whole S1→S4 pipeline, with S2 redaction expressed as a
  **strict gate** (UP already supports `blocked` / gate semantics).

So: adopt UP's spine (MCP-stdio server, YAML phases, phase-ledger producer/verifier/critic, gates,
feedback/rerun, artifact export) for orchestration and evaluation; add audio-processing phases in
front. This maximizes reuse where UP is strong and confines new build to the genuinely new (audio).

**Extensibility — confirmed against the UP source (resolves OQ-3):**

- **Extension mechanism:** phase types are a hardcoded `if/elif` chain in
  `WorkflowRunner._run_workflow` (`engine/runner.py:83-114`), ending in
  `raise ValueError("Unsupported phase type: ...")`. **No plugin registry** — extending means adding
  `elif phase.type == "audio_redaction"` branches plus `_run_*_phase` methods, and (optionally) a
  config dataclass like `PhaseLedgerLoopConfig`. Per-phase `config` is arbitrary passthrough, so
  wiring new phase config is trivial.
- **Directly reusable for S4:** `phase_ledger_loop` scores a `source_text` through
  producer→verifier→critic against a contract (`runner.py:147-160`) — the exact call-scoring shape.
  Gates, `feedback`/`rerun`, and `export_artifacts` are reusable as-is.
- **The one real gap — text/JSON-centric artifact model:** `PhaseState.output` is a `str`
  (`state/store.py:23`) and runs serialize to JSON; phase sources are text-only
  (`runner.py:426-433`). Audio has no native artifact type. **Fix, in two parts:**
  - *Binary handoff (audio phases S1→S3):* pass the raw and compliant recordings as **file-path
    references in `run.context`**, mirroring how `_run_ingestion_phase` stores `document_paths`
    (`runner.py:130-145`). New code, established pattern.
  - *Evaluator inputs (S4):* the phase-ledger evaluator validates every `source_quote` as an **exact
    substring of its text `source_text`** (`manager.py:178-187,362-370`), and `source_text` comes only
    from text phase-outputs (`runner.py:426-433`). So **S4's scored inputs must be text**: the S3
    transcript and the S3' prosody **feature summary** (FR-3'.2), delivered via
    `input.source: subscribed_phase_outputs`. Prosody must **not** be handed to S4 as a context file
    path — the loop cannot read it. This is also why NFR-5 auditability works: every finding cites an
    exact line of that text source.
- **Branch-dependent scoring vs the static contract (resolves SGAP-002):** contract `categories` and
  per-category `minimum_count` are **static** (`manager.py:188-202`); a single contract with minimums
  would raise a false `manager-minimum-count` failure for elements legitimately absent on a call's
  branch. **Fix:** a call-path classification step (FR-4.1) **selects the applicable per-branch
  contract** (route → contract), and/or branch-conditional mandatory elements use `minimum_count: 0`
  with applicability enforced in the producer/verifier role prompts rather than the deterministic check.

**Decision recorded:** fork-and-extend UP. The UP repo is our own (no external authorization gate).
Reuse S4 evaluation + gates + export + feedback/rerun; build new audio-phase handlers for S1–S3'.

## 10. Open questions (status)

- **OQ-1 — RESOLVED:** intonation/emotion is scored from a **parallel prosody path** (S3') off the
  compliant recording, fed into S4 with the transcript. *(See §3.4, FR-3', FR-4.4/4.5.)*
- **OQ-2 — RESOLVED:** compliance-first. Redaction removes PII from everything downstream; mandatory
  elements whose content **is** that removed PII are **not scored for now**. *(See §3.5, FR-4.2.)*
- **OQ-3 — RESOLVED:** UP is extensible to audio phases by fork-and-extend (hardcoded phase dispatch
  at `runner.py:83-114`; no plugin registry). Real gap is the text/JSON-centric artifact model — audio
  passes as file-path references in `run.context`. The repo is our own, so there is no authorization
  gate. Decision: fork-and-extend. *(See §9.)*
- **OQ-4:** Recording format/codec, mono vs stereo (stereo eases diarization), sample rate, and how
  recordings are delivered (drop folder, API, telephony platform export)?
- **OQ-5:** Do we get the agent's post-call system entries (order/address/comment/result) for
  cross-checking, and via what interface?
- **OQ-6:** Retention, access-control, and audit requirements for recordings, transcripts, and
  evaluations.
- **OQ-7:** Expected call **volume** (per day/agent) and turnaround (near-real-time vs nightly batch).
- **OQ-8:** Is the current `CallScript.docx` the single active script, or one of several campaigns?
  How often does it change (the rubric must be versioned against the script version)?
- **OQ-9:** The **forbidden-words list** (FR-1.3) — `FirstWorkflow.md` L13 says forbidden words exist but
  does not list them. We need the actual list (and the required-verbatim phrasings, if maintained
  separately) from the client. Needed before forbidden-word scoring can be built.
- **OQ-10:** The **per-client offer data** (FR-1.3) — individualized price/channels/Mbps per call. Do we
  receive it, in what form, and keyed how to the recording? Needed before value-correctness scoring
  (§3.6) is possible.

## 11. The "several interconnected workflows" (client's framing, L23)

The client says these are several linked workflows and to focus first on the evaluation. A natural
decomposition:

1. **W1 — Call intake & compliance** (S1–S2): ingest + redact → compliant recording. *(First to build;
   everything gates on it.)*
2. **W2 — Transcription** (S3): compliant recording → diarized Bulgarian transcript.
3. **W3 — Performance evaluation** (S4): the phase-ledger scoring workflow. *(The client's stated
   first focus.)*
4. **W4 — Aggregate analytics** (later): success-template and break-point mining across agents.
5. **W5 — Customer-emotion analysis** (explicitly "later", L11).

## 12. Next steps

- **Resolve remaining §10 open questions** — OQ-1, OQ-2, and OQ-3 are resolved. The remaining ones
  (OQ-4 through OQ-8: recording format/delivery, agent system entries, retention/access, volume, script
  versioning) are **operational details, not planning blockers** — they can be settled during planning.
- **Hardening (default for build-bound research) — COMPLETE.** All three gates ran and converged:
  `doc-gap-closure-loop` (internal readiness) → `requirements-coverage-gap-loop` (breadth) →
  `requirements-satisfaction-gap-loop` (depth). Audit trails: `*.gap-audit.md`, `*.coverage-audit.md`,
  `*.satisfaction-audit.md`. Open items OQ-4–OQ-10 are operational inputs to settle with the client
  during planning, not blockers.
- **This document is ready to become a Plan** (plan-playbook) for W1 (intake + redaction) and W3
  (evaluation).
