# Call-Center Harness — STT Engine Decision (Research)

> Decision requested: which speech-to-text engine to build W2 (transcription) on, before processing
> real PII audio. Constraints from the requirements foundation: Bulgarian, 8 kHz telephony, speaker
> separation, **word-level timestamps** (needed to map detected PII → audio spans for the FR-2.4
> redaction map), dialer-scale throughput, and — decisively — **compliance** (raw PII audio must stay
> off non-DPA third parties). Facts below are verified against vendor docs (July 2026); confidence noted.

## Constraints → what actually differentiates

1. **Compliance (hard):** engine must run either self-hosted, or as an EU-region cloud service under a
   DPA with no-training-on-data. This filters the field more than accuracy does.
2. **Bulgarian support** at usable accuracy on 8 kHz telephony.
3. **Speaker separation** — either native diarization *or* our recordings' stereo channels already
   separate agent/customer (our sample is **8 kHz stereo** — unverified whether dual-channel; if it is,
   native diarization stops mattering).
4. **Word-level timestamps** — required for redaction span-mapping. All serious engines provide this.
5. **Ecosystem fit:** the UP harness we're forking already runs on **Azure** (Key Vault `hrness`,
   `infra/azure`). An Azure-native STT minimizes new infra + secrets surface.

## Comparison (verified)

| Engine | Bulgarian | Diarization (bg) | Word timestamps | Compliant deployment | Notes |
| --- | --- | --- | --- | --- | --- |
| **Azure AI Speech** | ✅ real-time + batch + **fast transcription**; custom speech (plain-text) [1] | ⚠️ feature exists (≤35 speakers) but docs only demo `en-US`; **verify for bg-BG** [4] | ✅ | EU region + DPA; **on-prem Speech container** option | Best ecosystem fit (harness already on Azure) |
| **Google STT V2** | ✅ chirp/chirp_2/**chirp_3**, long/short; **EU region** (europe-west4/eu) [2] | ❌ **not supported for bg-BG** (no Bulgarian entry lists diarization) [2] | ✅ (word-level confidence/time) | EU endpoints + CMEK + DPA | Bulgarian diarization gap is decisive unless we rely on stereo |
| **Deepgram** | ✅ dedicated Bulgarian model [3] | ✅ confirmed for Bulgarian [3] | ✅ | **Self-hosted / on-prem** available [3] | New vendor; self-host path is compliant |
| **Whisper (self-hosted:** faster-whisper / whisperX) | ✅ (99 langs; **no official bg WER**; Slavic/Russian ~8–14%) [5] | ❌ native — pair with pyannote or use stereo channels | ✅ (whisperX/faster-whisper) | **Fully self-hosted → max compliance, zero egress, no per-call cost** | Best for local dev + as fallback; accuracy on 8 kHz bg unverified |

## The stereo caveat (materially changes the diarization column)

Our sample is **8 kHz stereo**. If the two channels are true dual-channel (agent on one, customer on the
other — common for call-center capture), we transcribe each channel separately and get **perfect
diarization for free, engine-independent** — which neutralizes Google's Bulgarian-diarization gap and
Whisper's lack of native diarization. This is a **2-minute, compliance-safe check** (decode channel
energy; no transcription, no egress) that should run before finalizing. Not yet verified (needs ffmpeg).

## DECISION (updated): self-hosted, bring-your-own-model

**Client constraint (2026-07-07): the client prefers their own (self-hosted) model.** This **rules out
cloud-SaaS as the production data path** — Azure AI Speech (cloud) and Deepgram (cloud) are therefore
**not** the production engine. The compliance benefit is maximal: **raw PII audio never leaves
client-controlled infra (zero third-party egress).**

- **STT is a self-hosted, pluggable model provider behind a fail-closed interface** (the same
  pluggable-engine pattern already locked in the requirements foundation). The client's own model drops
  into this interface; the harness is model-agnostic.
- **Reference/default implementation → self-hosted faster-whisper / whisperX (`bg`)** for our dev, for
  processing the first PII sample on-machine, and as the fallback. It is not a hard dependency.
- **Diarization** comes from the **stereo channel split** (if recordings are true dual-channel — still
  the 2-minute check) or a **self-hosted diarizer (pyannote)** — never a vendor.
- **Word-level timestamps** (for the FR-2.4 redaction map) are provided by whisperX / faster-whisper and
  must be a required capability of whatever model is plugged in.

Cloud engines (Azure/Google/Deepgram) are retained in the comparison only as **rejected alternatives**
(the client's own-model preference is the deciding constraint), not as the chosen path.

### Resolved (2026-07-07): (b) self-hosted, we select the open model — with a hard no-leak bar

The client wants it self-hosted/controlled and leaves the model choice to us, **provided it is GDPR
compliant and has no way to leak the source audio / what it can access.** W2 is therefore a **selection**
task, and the selection is constrained by an air-gap requirement:

- **Chosen model:** open Whisper-family — **faster-whisper** (CTranslate2) default; **whisper.cpp** as the
  cleanest air-gap alternative (pure-local, manually-placed GGML weights). Both run **fully offline** at
  inference; word-level timestamps available (whisperX / faster-whisper).
- **No-leak guarantee is architectural, not trust-based:** every stage touching source/compliant audio
  runs in a **network-egress-denied deployment**, with **model weights vendored/pre-placed** (no runtime
  fetch; `HF_HUB_OFFLINE=1` / local-files-only) and **no telemetry**. There is no outbound route, so audio
  cannot be exfiltrated even by a misbehaving dependency.
- **Diarization** self-hosted under the same boundary: stereo channel-split (if dual-channel) or pyannote
  with **vendored weights**.
- To verify at build time: confirm the chosen stack makes **zero network calls** during a transcription
  run (e.g. run it with outbound network blocked and confirm success).

## Confidence & what remains to verify

- **High confidence:** Bulgarian support for Azure [1], Google [2], Deepgram [3]; Google's Bulgarian
  diarization gap [2]; self-host paths for Whisper/Deepgram.
- **Verify before locking:** (a) Azure `bg-BG` diarization (docs only demo `en-US`) [4]; (b) whether our
  recordings are true dual-channel stereo (the free-diarization question); (c) real Bulgarian WER on 8 kHz
  for the shortlisted engines — measurable only once we transcribe a labeled sample.

## Sources

- [1] Azure Speech language support (STT) — https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=stt
- [2] Google Cloud STT V2 supported languages — https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages
- [3] Deepgram Bulgarian STT — https://deepgram.com/product/speech-to-text/bulgarian
- [4] Azure real-time diarization — https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-stt-diarization
- [5] Whisper WER by language/condition — https://vexascribe.com/how-accurate-is-whisper

## Next action

Confirm the engine choice. On confirmation, the immediate compliance-safe step is the **stereo
channel-separation check** on the sample (decode only), which decides whether native diarization is even
needed — then a local Whisper transcription pass to produce the first real Bulgarian transcript on-machine.
