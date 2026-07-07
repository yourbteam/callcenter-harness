# Implementation Plan — Callcenter Harness (First Slice)

> Turns the triple-gated research (`docs/research/callcenter-harness-requirements-foundation.md`,
> `…-stt-engine-decision.md`, `…-redaction-method-research.md`) into a buildable plan. Scope: W1 (intake +
> air-gapped redaction), W2 (per-channel STT + prosody), W3 (evaluation). Base: fork/extend the United
> Partners harness (`~/united-partners`). Decisions are **locked** (P2); genuine open items are in §9.

## 0. Locked architectural decisions

1. **Fork-and-vendor the UP engine as `cc_harness`.** Copy the UP engine module structure
   (`src/up_harness/engine/runner.py` dispatch, `src/up_harness/phase_ledger/`,
   `src/up_harness/state/store.py`, `src/up_harness/server/mcp_stdio.py`) into a new `src/cc_harness/`
   tree. Rationale: §9 of the requirements foundation (reuse the phase-ledger evaluation loop, gates,
   feedback/rerun, artifact export; the audio front-end is net-new either way).
2. **New phase types, added to the runner's `if/elif` dispatch** (mirrors `src/up_harness/engine/runner.py:83-114`):
   `audio_ingest`, `audio_redaction`, `transcription`, `prosody`, and **`call_path_classify`**. Evaluation
   reuses `phase_ledger_loop`. **Note (net-new, not UP reuse):** UP's existing `route_decision`
   (`_run_route_decision_phase`, `runner.py:162-169`) is a keyword router over `inputs["prompt"]` that
   selects a *workflow* — it does **not** read transcripts. Call-path classification is **new logic** in a
   new `call_path_classify` phase (see §5), not a reuse of `route_decision`.
3. **Binary artifacts as file-path references in `run.context`** (mirrors `_run_ingestion_phase`
   `runner.py:130-145`). `PhaseState.output` stays text (a JSON summary + the artifact path).
4. **Air-gap is enforced by deployment, not trust** (NFR-7): every audio-touching phase runs with
   `HF_HUB_OFFLINE=1`, vendored weights, and in a network-egress-denied environment. Acceptance test: the
   full W1→W2 run succeeds with outbound network blocked (reuse `setup_airgapped_stt.sh verify` pattern).
5. **Pluggable, fail-closed engine interfaces** for STT, redaction-NER, and prosody: if the engine/model
   is not configured, the phase **blocks** (like UP command mode), never silently degrades.
6. **Redaction ordering (surfaced by planning — see §3.2):** transcribe the **raw** audio ephemerally to
   locate PII, mask the audio → **compliant recording**, **discard the raw transcript**, then transcribe
   the **compliant** recording for evaluation. The eval transcript is therefore intrinsically PII-free
   (masked spans are silence). This honors the client flow literally and is the guarantee's backbone.
7. **Runtime contract selection requires an engine change (net-new — the branch-scoring gap).** UP's
   `phase_ledger_loop` reads `phase_contract_path` **statically from the phase's own YAML config**
   (`phase_ledger/config.py:29,46-49`, consumed at `runner.py:147-148`); nothing reads `run.context`. So
   "classify → select the per-branch contract" is **not** supported as-is. **Locked mechanism:** extend
   the forked `_run_phase_ledger_phase` so the contract path may be **overridden from a context key** that
   `call_path_classify` writes (falling back to the static YAML path when absent). *(Alternative
   considered and rejected: one YAML workflow per call-path family — rejected because it duplicates the
   whole pipeline per branch.)* This engine change is part of M5.

## 1. Prerequisites (client-dependent — build proceeds; these gate specific acceptance items)

| prerequisite | blocks | until then |
| --- | --- | --- |
| Labeled PII ground-truth set | redaction **recall sign-off** (NFR-6/OQ-6) | build + unit-test on our 1 sample; recall unverified |
| Residual-PII target (OQ-6) | redaction "done" definition | use over-redaction default; target TBD-by-client |
| Forbidden-words list (OQ-9) | forbidden-word scoring (FR-4.2) | recognizer wired, list empty |
| Per-client offer data (OQ-10) | value-correctness scoring (requirements §3 decision 6 "Structure vs value scoring" / OQ-10) | structure/order scoring only |
| Labeled call-path + outcomes | eval accuracy measurement | mechanism built, accuracy unverified |

**Out of scope (this slice):** W4 analytics, W5 customer-emotion, data-entry-accuracy eval, value-correctness scoring.

## 2. Repo layout

```
callcenter-harness/
  src/cc_harness/
    engine/runner.py            # forked UP runner + new phase handlers
    engine/workflow.py          # forked
    phase_ledger/               # forked (evaluation loop, unchanged)
    state/store.py              # forked (+ artifact-path helpers)
    audio/ingest.py             # S1: accept, non-conversation detect, channel split
    audio/redact.py             # S2: Presidio detect → span→time map → ffmpeg mask
    audio/stt.py                # S3: wraps scripts/transcribe_airgapped.py, per-channel
    audio/prosody.py            # S3': feature summary (text) per turn
    contracts/                  # per-branch evaluation contracts (authored from CallScript)
    server/mcp_stdio.py         # forked MCP entry
  scripts/setup_airgapped_stt.sh, transcribe_airgapped.py   # exist, reused
  workflows/callcenter-call-qa.yaml
```

## 3. W1 — intake + redaction

### 3.1 S1 `audio_ingest`
- Input: recording path + metadata (agent id, timestamp, campaign) in `run.context`.
- **Non-conversation gate (FR-1.2):** ffmpeg loudness/VAD + min-duration threshold (default 8 s, config);
  no-answer/voicemail/short → phase sets `status=skipped`, run ends with `non_conversation`.
- **Channel split:** `ffmpeg -filter_complex channelsplit` → `left.wav`, `right.wav` (paths in context).
  (Sample verified dual-channel; if mono, fall back to a single stream + pyannote diarizer — later.)

### 3.2 S2 `audio_redaction` (air-gapped, per channel)
Per channel:
1. **STT(raw channel)** ephemeral → word-timestamped transcript (reuse `transcribe_airgapped.py --channel`).
2. **Detect PII** — Presidio `AnalyzerEngine` with `language="bg"` and **all recognizers registered for
   `bg`**: pattern recognizers (EGN+checksum, phone, IBAN, card+Luhn, numeric-run catch-all), context
   recognizers (lead-ins "на адрес","г-н/г-жа","ЕГН","телефон","клиентски номер"), NLP engine = transformers
   BG NER (`iarfmoose/roberta-small-bulgarian-ner`), plus **GLiNER** union. Input text = **raw
   concatenation of `word` strings** (they carry leading spaces) with a char→word-index map.
3. **Map spans → audio time** via the covered tokens' `start/end`; union + **pad ±250 ms**; number runs
   fall back to **segment-level** ranges (digit-token timestamps unreliable).
4. **Mask** with ffmpeg `volume=enable='between(...)+…':volume=0` → masked channel.
5. **Discard the raw transcript** (never persisted outside the air-gap).
- Recombine masked L/R → **compliant recording** (path in context).
- **Redaction map** (FR-2.4): `[{start,end,category,channel}]`, no values → `redaction-map.json`.
- **Hold gate (FR-2.3):** if STT confidence or detector coverage below threshold → run `blocked`
  (`held_for_review`), nothing downstream.

## 4. W2 — transcription + prosody (off the compliant recording)

### 4.1 S3 `transcription`
- STT(**compliant** recording), **per channel** → diarized eval transcript + `words.json`. Masked spans =
  silence → intrinsically PII-free. `input.source` for S4 = `subscribed_phase_outputs`.

### 4.2 S3' `prosody`
- Extract pitch/pace/energy/pause per turn from the compliant recording (parselmouth/librosa, vendored),
  emit a **text feature summary** as the phase output (per requirements FR-3'.2), subscribed by S4.

## 5. W3 — evaluation (reuse `phase_ledger_loop`)

- **Classify call path** (new `call_path_classify` phase — **not** `route_decision`, §0.2): reads the eval
  transcript and determines call-type (first-contact vs callback), offer accepted, e-sign vs courier,
  device vs none, cross-sell branch, then **writes the selected per-branch contract path to a context key**
  the evaluate phase reads (the engine override of §0.7).
- **Per-branch contracts** authored from `CallScript.docx` (§6 of requirements): each is a phase contract
  with `categories` = the mandatory elements for that path, verbatim-required vs semantic tagged,
  `minimum_count` per category. Universal (call-agnostic) intonation/active-listening categories included.
- **Evaluate:** `phase_ledger_loop` producer→verifier→critic over `subscribed_phase_outputs` (transcript +
  prosody summary). Masked spans treated indeterminate (FR-4.2). Forbidden-words from the FR-1.3 list.
- **Output:** per-call QA report (scores per dimension, findings with exact quotes, duration/outcome) via
  `export_artifacts`. Team-leader `submit_feedback` + `rerun` reused as-is.

## 6. Workflow YAML (`callcenter-call-qa.yaml`)

Phases: `ingest` → `redact` (hard gate) → `transcribe` ‖ `prosody` → `classify` (`call_path_classify`) →
`evaluate` (phase_ledger_loop, contract path from the classify context override, §0.7) → `report`
(deliverable/export). `redact`
and `ingest` block the run on their gates; `transcribe`/`prosody` subscribe to `redact`'s compliant-audio
path; `evaluate` subscribes to `transcribe`+`prosody`.

## 7. Build sequence (milestones, each independently verifiable)

1. **M1 — fork skeleton:** `cc_harness` engine boots, `workflow.list`/`start` work on a no-op workflow.
2. **M2 — S1 ingest + channel split:** run on the sample; produce L/R wavs + non-conversation gate.
3. **M3 — S2 redaction:** Presidio+NER+GLiNER wired air-gapped; run on the sample; produce compliant
   recording + redaction map; **verify with network blocked**.
4. **M4 — S3/S3':** per-channel eval transcript (PII-free) + prosody summary off the compliant recording.
5. **M5 — W3 eval:** the `call_path_classify` phase + the `_run_phase_ledger_phase` **context contract-path
   override** (§0.7); one per-branch contract authored; classify selects it; `phase_ledger_loop` scores the
   sample transcript. **Also implements the §7 per-channel masking bound** (deferred from M3): M3 masks
   both channels uniformly (recall-safe over-mask); M5 identifies the agent vs customer channel (from the
   classification) and bounds agent-channel masking to recited-customer-PII so agent script delivery stays
   assessable for eval dims 2–3. **And the FR-3.2 speaker relabeling** (deferred from M4): M4 labels the
   transcript/prosody by physical channel (`left`/`right`); M5's channel-role ID relabels them
   agent/customer so S4 can score agent-vs-customer turns (adherence, objection/rebuttal pairing).
6. **M6 — end-to-end YAML:** the full pipeline runs `ingest→…→report` on the sample, air-gapped.

## 8. Acceptance criteria

- Full pipeline runs on the sample **with outbound network blocked** (NFR-7) → compliant recording +
  redaction map + eval report.
- Compliant recording: manual check that masked spans align to detected PII (recall measured once labeled
  set arrives).
- Eval transcript contains no PII (masked = silence).
- Per-branch contract selection matches the sample's call path; no false `manager-minimum-count` on absent
  branches.
- `cc_harness` unit tests + a fixture-backed dry canary (mirroring UP's `verify_harness.py`).

## 9. Decisions locked (previously flagged as questions — resolved from grounding)

- **P-1 — redaction ordering: LOCKED to re-transcribe the compliant recording** (§0.6). Rationale: the
  eval transcript is PII-free by construction and everything downstream provably derives from the masked
  recording (cleanest audit story for a compliance-obsessed client); this matches the client's literal
  stated flow. Cost = a 2nd STT pass per call, which is cheap next to the compliance posture.
- **P-2 — LOCKED to fork-and-vendor** the UP engine (§0.1); a submodule buys upstream tracking we don't
  need for a first slice.
- **P-3 — DONE:** the requirements doc (§4) now documents the ephemeral raw-transcript detection step, so
  the pipeline wording matches this plan.

*(No open decision blocks the build. The next mode is Write code, brought to Kamen as granular,
approval-gated changes per G11 — starting M1.)*

## 10. Known limitations (implemented so far; deferred by design)

- **Verbatim-vs-semantic scoring (FR-4.2):** the deterministic evaluator matches mandatory elements by
  case-insensitive keyword/stem substring. The verbatim-required vs semantic-match distinction needs
  embeddings or command-backed model roles — **deferred**; contract categories are keyword-anchored today.
- **Multi-branch contract selection (§5):** only the `callcenter-newplan-esign` contract is authored, so
  `call_path_classify` selects it unconditionally (it does identify the agent channel and hold when it
  can't). True branch detection (offer 1/2/3, e-sign vs courier, device, cross-sell, callback) arrives as
  more contracts are authored — **deferred**.
- **Intonation/active-listening depth:** a deterministic prosody proxy flags low-energy/off-band-pace
  delivery (a named failure pattern). Nuanced emotion/active-listening scoring needs command-backed model
  roles (UP `execution_mode=command`) — **deferred**; the prosody summary is already in the packet.
- **Recall measurement:** redaction recall is unmeasured until the client's labeled ground-truth set +
  residual-PII target (OQ-6).
