# Call-Center Harness — Inputs to Gather Before Build

> Decision (this session): **gather inputs first**, then build. This checklist is the gate. It turns
> the requirements foundation's open questions (OQ-4–OQ-10) plus the engine/data decisions into an
> owned, prioritized to-do list. Source of requirements: `callcenter-harness-requirements-foundation.md`.

## Why this comes first

The compliance-critical steps (GDPR audio **redaction** → **STT**) cannot be built *or verified*
without real sample recordings and a chosen approach. A pipeline we can't run on real Bulgarian calls
isn't a working version — it's scaffolding. So the top priority is the one input that is both **build
material and the test set**: a labeled sample recording set.

## P0 — Blocks everything (get these first)

| # | Input | Owner | What it unblocks | Notes / spec |
| --- | --- | --- | --- | --- |
| 1 | **Labeled sample call recordings** | Client (A1) | Building AND verifying W1 redaction + W2 STT; the redaction-recall and STT-accuracy gates | Need coverage of the real branch space: Offer 1/2/3 accepted, e-sign vs courier, device vs none, cross-sell (MBB/Netbox), callback (CS L104), rich objection calls, plus **non-conversation** examples (no-answer/voicemail/hang-up). Ground truth per call: which PII is spoken, and the outcome. Target count to agree (suggest ≥30–50 across paths). |
| 2 | **Recording format & delivery** (OQ-4) | Client (A1) | S1 ingest; diarization approach | Codec/container, **mono vs stereo** (stereo = separate agent/customer channels → far better diarization), sample rate, and how we receive them (drop folder, API, telephony export). |
| 3 | **Redaction approach decision** | Us (bteam) | W1 — the compliance core | Concrete method + a way to **measure PII recall** (NFR-6 over-redaction bias). EGN is a structured 10-digit token (detectable); names/addresses/phones are harder. Likely: STT+NER over time-aligned transcript → mask audio spans + emit the FR-2.4 redaction map. Depends on #1 to measure. |
| 4 | **Bulgarian STT engine decision** | Us (bteam) | W2 transcription; and W1 if redaction is transcript-driven | Must handle Bulgarian + telecom jargon and support (or pair with) **diarization**. Options to evaluate: Azure Speech, Google STT, Whisper-family. Decision + access/credentials. |

## P1 — Blocks the evaluation stage (W3) doing its full job

| # | Input | Owner | What it unblocks | Notes |
| --- | --- | --- | --- | --- |
| 5 | **Forbidden-words list** (OQ-9) | Client (A1) | FR-4.2 forbidden-word flagging | `FirstWorkflow.md` L13 says these exist but doesn't list them. Also: any **required-verbatim phrasings** maintained separately from the script. |
| 6 | **Per-client offer data feed** (OQ-10) | Client (A1) | §3.6 value-correctness scoring (did the agent quote the *right* price/channels/Mbps) | The individualized offer per call, and **how it keys to a recording** (call ID / phone / agent+timestamp). Without it, W3 scores structure only, not value. |
| 7 | **Model command for evaluator roles** | Us (bteam) | W3 producer/verifier/critic (UP `UP_HARNESS_AGENT_COMMAND`) | Which LLM + access. Deterministic dry-run works without it; live scoring needs it. |
| 8 | **Prosody library decision** | Us (bteam) | S3' feature extraction (FR-3') | praat-parselmouth / librosa / openSMILE. Low-risk; pick during build. |

## P2 — Needed before production, not before first build

| # | Input | Owner | What it unblocks | Notes |
| --- | --- | --- | --- | --- |
| 9 | **Agent post-call system entries** access (OQ-5) | Client (A1) | Later W4 data-entry cross-checks | Interface to order/address/comment/result. Out of first-slice scope per §5. |
| 10 | **Retention / access / audit + DPA** (OQ-6) | Client (A1) + Legal | NFR-2 storage/retention; lawful handling of PII-bearing recordings | Data-processing agreement for us to hold A1 call recordings; who may view evaluations; retention windows; residual-PII tolerance target. |
| 11 | **Volume & turnaround** (OQ-7) | Client (A1) | NFR-3 batch/async sizing; FR-1.2 non-conversation thresholds | Calls/day/agent; near-real-time vs nightly. |
| 12 | **Script canonicity & versioning** (OQ-8) | Client (A1) | Rubric versioning; per-branch contracts | Is `CallScript.docx` the single active script or one campaign of several? Change cadence. |

## What can start in parallel (no external blocker)

- **Author the branch-dependent evaluation contracts** from the script rubric (§6) — the per-branch
  phase contracts for the UP-forked evaluator. This is grounded in `CallScript.docx` we already have.
- **Stand up the UP-forked harness spine** (pipeline phase types, fail-closed engine interfaces) as a
  skeleton — but per the chosen sequence, hold implementation until P0 inputs land.

## Sequencing

```
P0 (sample audio + format + redaction method + STT engine)  ──►  build+verify W1 (redaction), W2 (STT)
P1 (forbidden-words + per-client data + model command)      ──►  build W3 (evaluation) full
P2 (retention/DPA + volume + versioning)                    ──►  production-readiness
```

W3's evaluation logic can be built and tested on **sample transcripts** as soon as P1 (items 5–7) land,
in parallel with P0 redaction/STT work — but a true end-to-end run needs P0 complete.

## Immediate next actions

1. **Client (A1) ask** — items 1, 2, 5, 6 (and start 9–12). Item 1 (labeled sample recordings) is the
   critical path.
2. **Us (bteam) decisions** — items 3, 4 (redaction method + STT engine). I can run a research pass on
   options (accuracy on Bulgarian, diarization, redaction-recall measurability) when you want it.
