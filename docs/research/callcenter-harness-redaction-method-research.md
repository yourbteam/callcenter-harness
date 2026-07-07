# Call-Center Harness — GDPR Audio Redaction Method (Research)

> Research for W1/S2: detect + mask PII in Bulgarian call recordings **fully offline/air-gapped**
> (NFR-7), **recall-biased** (NFR-6), producing a **compliant recording** + a **redaction map**
> (FR-2.4), built on the **word-level-timestamped transcript** the STT stage now produces
> (`airgapped-local-bulgarian-stt`). Build-bound. Facts cited to sources (July 2026); inferences marked.

## 1. Approach (and the one rejected)

**Chosen: transcript-driven redaction.** STT → PII detection over the transcript text → map each
detected span back to audio time via word timestamps → mute/beep those audio ranges → compliant
recording + redaction map. This is the established pattern (Presidio analyzes text; the audio companion
is timestamp-mapping) [1].

**Rejected: audio-domain PII detection** (detect PII directly in the waveform without a transcript) —
not mature, no offline tooling; would be a research project of its own. *(Inference.)*

Everything runs offline with **vendored models** inside the same network-egress-denied boundary as STT
(NFR-7). Presidio, GLiNER, and HF NER models all run locally once weights are downloaded [1][2][4].

## 2. PII taxonomy and per-type detection

| PII type | Detection | Recall notes |
| --- | --- | --- |
| **EGN** (ЕГН, 10-digit civic number) | Regex `\d{10}` + **checksum validator**: weights `[2,4,8,5,10,9,7,3,6]` over digits 1–9, `sum % 11`, if `==10`→`0`, compare to digit 10 [3] | Also flag **any 10-digit run** even if checksum fails (STT may corrupt a digit) — over-detect |
| **Phone** | BG patterns: mobile `08[7-9]/098/099…`, `+359 8/9…`, landline `0`+area | Catch any 7–13 digit run near lead-ins ("телефон","мобилен","номер") |
| **IBAN / card** | BG IBAN (`BG` + 20 alnum, 22 total); card = 13–19 digits + **Luhn** | Union with generic long-digit-run catch |
| **Name** (customer PER) | Offline **Bulgarian NER** (§4) + **context recognizer**: tokens after "г-н"/"г-жа"/"господин"/"госпожо" | NER is the weak link (§5) → also mask context-lead-in followers |
| **Address** (LOC) | NER LOC + **lead-in patterns**: after "на адрес", "ул.", "бул.", "ж.к.", "гр.", "с." mask following tokens up to a boundary | Grounded in the script's own phrasing (`CallScript.docx` L4, L19) |
| **Email** | Presidio built-in regex | Rare in calls |
| **Date of birth** (spoken, distinct from EGN) | Date pattern + context ("роден", "дата на раждане") + NER DATE | Often embedded in EGN, but may be stated separately |
| **Account / customer / contract IDs** (Моят А1 login, customer no., contract no.) | Numeric-run + context ("клиентски номер", "договор", "Моят А1", "абонатен") | Union with the generic numeric-run catch-all |

## 3. Tooling recommendation

**Microsoft Presidio as the orchestration framework** [1], because it is purpose-built for exactly this
and runs offline:

- **Custom pattern recognizers** for the structured types — EGN (regex + checksum), phone, IBAN, card
  (Luhn) — with **context words** to boost confidence near lead-in phrases [1].
- **NLP engine** for PERSON/LOCATION set to an **offline Bulgarian NER** (§4) — Presidio accepts
  spaCy / Stanza / transformers backends [1]. **Since spaCy has no Bulgarian pipeline, Presidio's `bg`
  NLP engine is configured as the transformers `NlpEngine`** (a BG NER model from §4), or **Stanza `bg`**
  — not spaCy. Presidio is invoked with `language="bg"`.
- Optional second detector: **GLiNER** (zero-shot, custom entity labels, CPU-friendly, offline; there is
  a first-party Presidio↔GLiNER integration) [2] — used to catch entities the primary NER misses
  (recall bias).
- Presidio returns **character spans** into the text we hand it. So we assemble that text by
  **concatenating the raw `words.json` `word` strings as-is** — faster-whisper tokens **already include
  their leading space** (verified: `' Алло,'`, `' добре'`), so we add **no** separators (a "space-joined"
  build would double the spacing and drift every offset). Build a **char-offset → word-index map** from
  those exact strings; a returned char span then resolves to the covered word tokens, each carrying
  `start/end` audio times. This is the concrete span→time bridge.
- **Language registration (critical):** Presidio's `analyze(language="bg")` runs **only** recognizers
  whose `supported_language` includes `bg`. Every pattern + context recognizer (EGN/phone/IBAN/card/
  numeric-run/lead-ins) must be **registered for `bg`** (or language-agnostic), and the NLP engine mapped
  for `bg` — otherwise detection is **silently empty**.

**Redaction (audio):** for each detected span, take the covered tokens' `start/end`, union + **pad** the
ranges (recall bias, e.g. ±250 ms), then mask with ffmpeg. For **many** ranges, either OR them in one
`volume` filter — `-af "volume=enable='between(t,t1,t2)+between(t,t3,t4)':volume=0"` — or chain one
`volume` filter per range (a beep tone is an alternative to silence). Output → **compliant recording**.
Emit the **redaction map** (FR-2.4): `[{start, end, category}]` — timestamps + category, **no PII values**.

## 4. Offline Bulgarian NER options (the weak link)

Structured PII (EGN/phone/IBAN/card) is solved by regex+checksum. **Names and addresses depend on
Bulgarian NER, which is the least mature piece.** Verified offline options:

- **`iarfmoose/roberta-small-bulgarian-ner`** — a Bulgarian-specific NER model [4]. Small; a natural
  first candidate.
- **`Davlan/xlm-roberta-base-wikiann-ner`** — multilingual WikiANN NER (PER/LOC/ORG); WikiANN includes a
  Bulgarian (`bg`) split [4].
- **GLiNER multilingual** — zero-shot; give it Bulgarian labels ("име", "адрес") at runtime [2]. Bulgarian
  coverage unverified — must be measured.
- spaCy `xx_ent_wiki_sm` / **Stanza `bg`** — usable but weaker.

**Recommendation:** union of a dedicated BG NER model + GLiNER + context/lead-in recognizers, taking the
**union** of hits (recall over precision). Pick the specific model empirically on the labeled set (OQ-6).

## 5. The two hard problems (depth)

**(a) Spoken numbers — the highest recall risk.** Whisper transcribes numbers **as digits by default**
[5] — good, because EGN/phone regexes then match. But two real hazards:
- **Digit-token timestamps are unreliable.** Alignment "has no phonemes to match" for a bare `2014`-style
  token [5], so the very spans we most need to mask (EGN/phone) may have imprecise word timestamps.
  **Mitigation:** for any number run, fall back to **segment-level** timestamps (mask the whole segment
  containing the number) and pad generously — over-mask, per NFR-6.
- **Number-word variants.** Occasionally Whisper emits number *words* ("осемдесет и пет"). **Mitigation:**
  a **custom** Bulgarian number-word→digit normalizer (a small hand-built word map — not an existing
  library; *inference*, build work) + a **catch-all "long numeric/number-word run" recognizer** that
  masks any run ≥ N tokens regardless of checksum.

**(b) Weak Bulgarian NER** (§4) → names/addresses may be missed. **Mitigations:** detector union;
script-grounded **context lead-ins** ("на адрес…", "г-н/г-жа…") that mask following tokens without needing
the NER to fire; over-redaction; and **hold-on-low-confidence** (FR-2.3).

## 6. Recall-first design (NFR-6)

- **Union, not intersection,** of all detectors — a hit from any recognizer masks.
- **Catch-all numeric-run** recognizer independent of checksum (STT-error resilient).
- **Context lead-in** recognizers grounded in the script's fixed phrasing.
- **Padding** around every masked range; **segment-level fallback** when word timestamps are unreliable.
- **Hold gate (FR-2.3):** if STT confidence or detector coverage is low, the call is held for review, not
  passed downstream.
- Over-masking benign audio is acceptable: the evaluator does not score PII elements (§3.5) and marks
  masked spans indeterminate (FR-2.4).

## 7. Dual-channel leverage

The recordings are dual-channel (validated). The **customer channel** is PII-dense (they state EGN,
address, phone). Run detection **per channel**; this also lets the redaction map attribute masked spans
to a speaker without needing a diarizer. *(Inference, grounded in the confirmed dual-channel finding.)*

**Cross-stage prerequisite (real dependency):** per-channel redaction requires the **STT stage to
transcribe per channel**. The current `scripts/transcribe_airgapped.py` **downmixes to mono** by default,
so S2 must first **split L/R with ffmpeg** and transcribe each channel (the script already exposes a
`--channel` arg for the isolated-channel path). Without this split, only a mono transcript exists and
per-channel detection/attribution is impossible.

**Masking bound (reconciles NFR-6 over-redaction with eval dims 2–3, requirement N1).** Over-masking is
applied freely on the **customer channel**; on the **agent channel** masking is **bounded to actual PII
utterances** (the agent *reciting the customer's* name/address — the agent's own self-identification is
retained per §7a), so the agent's script delivery — needed for
intonation/emotion and active-listening scoring (FR-4.4/4.5) — stays assessable. The eval already does not
score the redacted PII elements (§3.5) and treats masked spans as indeterminate (FR-2.4).

## 7a. Scope boundaries (explicit)

- **Agent identity is retained,** not redacted. The QA harness must attribute the call to the agent
  (that is the point), and the agent is not the protected data subject of this customer-PII redaction.
  *(If employee-PII handling is later required, that is a separate scope.)*
- **The customer's voice is retained** in the compliant recording. Redaction removes spoken PII *content*
  (names/numbers/addresses); it does **not** remove the voice itself, because delivery/emotion/active-
  listening QA needs the audio and the recordings are client-owned. This is an accepted retention, called
  out so it is a decision, not an omission.

## 8. Measurement — how we prove recall (and what blocks it)

NFR-6's guarantee is only real if measured. **Recall = fraction of true PII spans masked.** That needs a
**labeled ground-truth set** (recordings with every PII span annotated) — checklist item 1 / OQ-6. With
one unlabeled sample we can validate the *mechanism* but not *recall*. **Blocking for a compliance sign-off:**
a labeled set + a residual-PII tolerance target (OQ-6). A recall-test harness (annotate → run → diff) is
part of the build.

## 9. S2 architecture (proposed)

```
compliant-audio ← ffmpeg mask(padded ranges)
        ▲
        │ time ranges (word ts → segment fallback, padded)
        │
PII spans ← Presidio(analyze) ← transcript + words.json (per channel)
   ├─ pattern recognizers: EGN(+checksum), phone, IBAN, card(Luhn), numeric-run catch-all
   ├─ context recognizers: "на адрес", "г-н/г-жа", "ЕГН", "телефон"
   └─ NLP engine: BG NER (iarfmoose / WikiANN-bg) + GLiNER (union)
        │
redaction-map.json ← [{start,end,category}]  (no PII values, FR-2.4)
        │
low-confidence? → HOLD (FR-2.3)
```
All components vendored + offline (NFR-7).

## 10. Open questions

- **OQ-6 (residual-PII tolerance):** what recall/residual target is acceptable for sign-off? Needed to
  define "done" for redaction.
- **Labeled ground-truth set:** required to measure recall (checklist item 1). Blocking for compliance sign-off.
- **BG NER model choice:** iarfmoose vs WikiANN-bg vs GLiNER — decide empirically on the labeled set.
- **Digit-timestamp reliability on real 8 kHz BG calls:** measurable now on our sample (compare word vs
  segment timestamps on the numeric runs) — a cheap early check.

## 11. Sources

- [1] Microsoft Presidio — customizing analyzer / NLP engines / languages: https://microsoft.github.io/presidio/analyzer/customizing_nlp_models/ , https://microsoft.github.io/presidio/tutorial/05_languages/
- [2] GLiNER (zero-shot NER) + Presidio integration: https://github.com/urchade/GLiNER , https://microsoft.github.io/presidio/samples/python/gliner/ , https://huggingface.co/knowledgator/gliner-pii-large-v1.0
- [3] Bulgarian EGN structure + checksum (weights 2,4,8,5,10,9,7,3,6; mod 11): https://github.com/miglen/egn , https://www.samiwell.eu/php/validate-bulgarian-id-number-egn
- [4] Offline Bulgarian NER: https://huggingface.co/iarfmoose/roberta-small-bulgarian-ner , https://huggingface.co/Davlan/xlm-roberta-base-wikiann-ner
- [5] Whisper number transcription (digits by default; digit-token alignment gap): https://github.com/openai/whisper/discussions/1041 , https://github.com/m-bain/whisperX/issues/300
