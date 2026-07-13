# Multi-Tenant "Hollow Profile" Architecture — research findings

**Status:** build-bound research (hardening via the three gates). **No code shipped.**
**Goal:** the harness is a generic engine; each client's script + requirements plug in as a JSON
**profile**. A1 is tenant #1. **Acceptance test (the definition of done):** a NEW client runs by adding
`profiles/<client>.json` (+ a language pack when the locale is new) with **ZERO code change**. Any value
in code that varies by client is a defect.
**Sources:** code audit (this session, file:line below); the M3 calibration spec
`docs/m3-calibration-spec.md`; the earlier cc-harness↔MAWF comparison.

---

## 1. Baked-in inventory (the defect surface — what must leave code)
Grounded audit of `src/` (only these carry client/locale-specific content; the rest is generic):
| # | Item | file:line | Varies by | Target layer |
|---|------|-----------|-----------|--------------|
| B1 | `SCRIPT_MARKERS` — A1 sales words used to pick the agent channel | redact.py:169-172, used :177 | **CLIENT** | profile.agent_markers |
| B2 | `CONTEXT_LEAD_INS` — PII lead-in cues (телефон/адрес/договор/абонатен…) | redact.py:22-26 | locale + light domain | language pack (+ profile extras) |
| B3 | `BG_NUMBER_WORDS` — spoken-number vocabulary | redact.py:30-40 | LANGUAGE | language pack |
| B4 | `GLINER_LABELS` — NER entity labels (име/фамилия/адрес…) | ner.py:24 | LANGUAGE | language pack |
| B5 | `DEFAULT_MODEL` — STT model path | stt.py:17 | deployment/lang | profile/deploy + language pack |
| B6 | A1 `contract_path` + `call_path` defaults | runner.py:278, 302 | **CLIENT** | required input (no default) |
| B3b | `_NUM_CONNECTOR = "и"` (connector between spoken numbers) | redact.py:40 | LANGUAGE | language pack |
| B7 | STT `language="bg"` default, never overridden by the runner (STT hardwired to Bulgarian) | stt.py:21,30; runner.py:163,233 | LANGUAGE | language pack (pass language) |
| B8 | **ЕГН (Bulgarian national-ID) checksum** — `EGN_WEIGHTS`, `egn_checksum_ok`, `"EGN"` classify | redact.py:19,50-57,87-88 | LOCALE | language pack (recognizer set) |
| B9 | **BG-IBAN** regex hardcodes the `BG` country prefix + BG length | redact.py:99 | LOCALE | language pack (recognizer set) |
| B10 | `persistence(...)` CALL SITE hardcodes the A1 offer category id `"offer1_discount"` | evaluator.py:131 | **CLIENT** | profile (offer-category id) |
| B11 | **The entire A1 contract file** — `categories_detail, ordering, ask_for_decision_phrases, objection_cues, prosody_thresholds, first_seconds, forbidden_words, required_phrasings` | contracts/callcenter-newplan-esign.json | **CLIENT** | profile (absorbs it — §8) |
| B12 | Workflow phase-config hardcodes A1 `call_path` + `contract_path` | workflows/callcenter-qa.json:15 | **CLIENT** | workflow refs `profile`, not contract/call_path |
| B13 | `first_seconds:{n,min_words}` opening-density thresholds | contracts/…json:27 | **CLIENT** | profile (rubric: `opening_density`) |

**Scope correction (Gate-2):** the §1 audit was `src/`-only and therefore missed the LARGEST client-config
artifact — the **contract file** (B11) — plus the workflow JSON (B12). These are the primary migration
sources: the per-client profile ABSORBS the contract (see §8).

**Correction to an earlier draft claim (Gate-1):** it is NOT true that "only the vocabulary is locale
data." Some **algorithms are locale-specific too** — the ЕГН checksum (B8) and BG-IBAN prefix (B9) are
Bulgarian, and the STT language code (B7) is hardwired. So the language pack owns a **recognizer SET +
params**, not just word lists: Luhn/email/digit-run recognizers are universal; ЕГН and IBAN-prefix are
per-locale recognizers the pack switches on.

**Genuinely generic (reusable as primitive BODIES — but the evaluate phase is substantially NEW):**
`check_ordering`, `check_forbidden`, `check_required_phrasings`, `first_seconds_engagement`,
`evaluate_prosody` (evaluator.py:60,80,87,94,342) take config lists — no A1 literals — and become the
bodies of ~4 primitives. **Honest scope (Gate-3 #5):** only ~4 of the ~14 §4 primitives have an existing
implementation; the rest (`slot_present, numeric_structure, state_machine, judge_check, deal_detect,
branch_params_present, path_select, variant_select, conditional_on, composite`) are net-new, and
`evaluate()`/`gap_checks` (the A1-shaped orchestrators + the hardcoded `adherence_score`) are REPLACED by
the rubric-interpreter, not kept. The ffmpeg `volume=0` masking, STT invocation, and prosody math are
client-agnostic. **Caveat (Gate-1 G3):**
the `persistence()` FUNCTION is generic but its **call site is not** — it reads the A1 category id
`"offer1_discount"` (B10); that id must come from the profile.

---

## 2. Three-layer model (what is code vs config, and why)
- **ENGINE (generic code, no client/locale literals):** the 6 fixed phase types
  (ingest→redact→transcribe→prosody→classify→evaluate), the redaction ALGORITHMS (regex/checksum/
  run-detection), the STT/prosody/ffmpeg mechanics, and the **check primitives** (§4). Knows *how*, never
  *what*.
- **LANGUAGE PACK (`languages/<lang>.json`, per locale):** B3 number-words, B3b connector, B2 PII cues,
  B4 NER labels, B5 default STT model, **B7 STT language code, B8 ЕГН checksum toggle, B9 IBAN country
  prefix** (the recognizer set + params, not just word lists). Shared across all clients in that locale.
- **CLIENT PROFILE (`profiles/<client>.json`, per client):** B1 agent markers, the **rubric** (typed
  checks, §4), call-path taxonomy, offer/objection state machine, legal variants, prosody thresholds,
  contract-key/id, language-pack ref. Knows *what*, never *how*.

**Scope boundary (explicit, to avoid rebuilding MAWF):** multi-tenancy is achieved by the fixed generic
phases consuming per-client DATA — NOT by making phase *dispatch* pluggable. The `if/elif` phase dispatch
(runner.py) stays; only the **evaluate** (and **classify**) phases become **hollow rubric-interpreters**
(a phase shell that runs a config-injected rubric, analogous to MAWF's hollow phase running config-
injected roles). Generalizing dispatch to a registry is a SEPARATE, optional change (see §9 Open-D1); it
is NOT required for the zero-code-change acceptance test.

---

## 3. Client-profile schema (v0 draft — to be hardened by the gates)
```jsonc
{
  "schema_version": 1,                     // engine checks compat → HOLD on mismatch (Gate-2 G6)
  "client_key": "a1",
  "language": "bg",                        // → languages/bg.json (B2-B5, B7-B9); missing/partial → HOLD
  "stt_model": "faster-whisper-small",     // optional override of language default
  "agent_markers": ["оферта","отстъпк","договор","месечна такса","канал","интернет", ...], // B1
  "call_paths": [                          // path taxonomy as DATA (M3 §1); checks bind via rubric[].applies_to_paths
    {"id":"titular",         "detect":{"primitive":"path_select","when":[...]}},
    {"id":"non_titular_yes", "detect":{...}, "gating":{"primitive":"phrase_present","phrases":["Вие ли вземате решение"], "answer":"yes"}},
    {"id":"non_titular_no",  "gating":{"phrases":["Вие ли вземате решение"], "answer":"no"}}
  ],
  // path→rubric binding (Gate-1 G8): each rubric[] check declares `applies_to_paths`; there are NO named
  // rubric groups — the "deal path checklist" = all rubric entries whose applies_to_paths includes that path.
  "service_branches": {                    // mobile vs fixed required params (M3 §3a)
    "mobile": {"required_params":["минути","роуминг","SMS","услуги селект","стандартна цена","промо цена"]},
    "fixed":  {"required_params":["канали","скорост","услуги селект","стандартна цена","промо цена","приемници"]}
  },
  "rubric": [                              // ordered list of TYPED CHECKS (M3 crit 1-16, E1-E8)
    {"id":"identify_a1", "primitive":"phrase_present", "phrases":["от името","А1"], "tier":"hard", "applies_to_paths":["titular","non_titular_yes","non_titular_no"]},
    {"id":"name_said",   "primitive":"slot_present", "slot":"NER_PER", "region":"intro", "tier":"hard"},
    {"id":"record_consent","primitive":"phrase_present","phrases":["записва"],"tier":"hard"},
    {"id":"price_structure","primitive":"numeric_structure","need":["standard","discount"],"tier":"hard","on_masked":"indeterminate"},
    {"id":"no_start_offer2","primitive":"phrase_ordering","before":"any_offer","not_first":["offer2_transition"],"tier":"hard"},
    {"id":"offer_flow","primitive":"state_machine","states":[...transitions declared as data...],"tier":"mixed"},
    {"id":"words_prefer","primitive":"word_prefer","words":["ще","отстъпка","получавате",...],"tier":"soft"},
    {"id":"words_avoid","primitive":"word_avoid","words":["купувате","таксуваме","можете",...],"tier":"soft",
       "except_in_mandated_spans":true},        // M3 §6 PRECEDENCE (G15)
    {"id":"legal_verbatim","primitive":"variant_select","variants_ref":"legal_variants", // single home (Gate-1 G9)
       "select_by":["offer_type","device"],"conditional_on":"deal","mask_aware":true,"tier":"hard"}
    // … remaining crit rows, each with applies_to_paths + tier …
  ],
  "offer_category_id": "offer1_discount",  // B10: the profile names its offer category (persistence call site)
  "prosody_thresholds": {"min_energy_db":..,"min_pace_wps":..,"max_pace_wps":..,"min_pitch_std_hz":..},
  "legal_variants": [ {"id":"V1","offer_type":"new_plan","device":false,"text_ref":"..."} , ... ]
}
```
The rubric entries are DATA; the engine ships the primitives that interpret each `"primitive": ...` type.

---

## 4. Generic check primitives (the evaluate phase's vocabulary — the whole point)
Each M3 requirement maps to a primitive; NONE needs A1 code. The engine implements the primitive once;
every client parameterizes it via JSON.
| Primitive | What it checks (generic) | M3 reqs it covers |
|---|---|---|
| `phrase_present` | any of N configured phrases appear (optionally in a region) | crit 2/3/4/8/13/14/15/16, identify_a1 |
| `phrase_ordering` | configured phrase-groups appear in a required order / not-first | ordering, "no start with offer 2" (§8) |
| `word_prefer` / `word_avoid` | count configured words as soft ± ; `except_in_mandated_spans` skips scripted/legal spans | §6 words + PRECEDENCE (G15) |
| `slot_present` | a redaction-map span of category X occurred in region R (DET-MAP proxy). **Granularity caveat (Gate-3 #1):** GLiNER labels name/address/org all as one `GLINER_PII` category (ner.py:100-101) and `_merge_ranges` collapses overlaps to `MULTI` (redact.py:234) — so `slot:"NER_PER"` is **too narrow** (misses GLiNER/context names) yet "any PII slot" is **too wide** (an address/org satisfies it). At current map granularity slot_present proves "a PII slot was masked here," NOT specifically "a name" → see §9 Open-D6 (enrich map labels, or accept the coarse proxy) | crit 1 name-said (limited), G6 phone/address captured (§14 R-a) |
| `numeric_structure` | ≥K distinct numeric values in a configured frame (e.g. standard+discount); `on_masked:indeterminate` | E8 price structure (§5) |
| `state_machine` | **(DET half only)** offer sequencing driven by configured **transition phrases** (offer1→offer2 via the P1 phrase; ≤2 rebuttals count) — genuinely data-driven on the agent channel | E5 offer sequencing (M3 §4/§8) |
| `judge_check` | **(NEW — Gate-3 #3)** a **semantic** check delegated to the command-mode LLM judge (needs the customer channel). Objection-**match** ("2nd objection matches the 1st") is NOT phrase-declarable data → it is a `judge_check`, not a `state_machine` transition. CMD | objection-match, active-listening, emotion (M3 §4/§14) |
| `deal_detect` | **(NEW — was missing, Gate-1 G5)** produce `deal`/`consent` state from configured signals (customer "да" + address-request + summary/legal). **CMD** (needs customer channel). This is E1; `conditional_on` depends on its output | E1 deal detection (M3 §2) |
| `branch_params_present` | **(NEW — Gate-1 G7)** given the detected service branch, check the branch's `required_params` phrases are present | E-branch, crit 5 (M3 §3a) |
| `path_select` | choose a call-path + its path-scoped rubric by configured signals. **titular/non-titular = CMD** (needs the customer answer to the gating question). **Service-branch (mobile/fixed) detection = DET** (agent-side service-type cue word, stereo; M3 §14) — a separate DET step, NOT bundled into the CMD path (Gate-2 G13b) | §1 titular/non-titular (CMD); mobile/fixed (DET) |
| `variant_select` | pick 1 of N configured legal variants by selectors; mask-aware closeness. **Bridge (Gate-3 #4):** masked spans are silence→no tokens, so they're already absent from `source_text`; the primitive reconstructs where deletions occurred by correlating the redaction-map time ranges (via E-8) against gaps in `agent_words` timestamps (which the evaluator already receives, runner.py:329) — alignment is computable, not string-only | E6 legal-verbatim (M3 §7) |
| `conditional_on` | wrapper: a check applies only when its condition holds. **Condition source ∈ {deal, consent (from `deal_detect`), refusal (Gate-2 G8, from `state_machine`/`deal_detect`), external}**. An **external** condition (e-sign, GDPR-on-file) has NO in-call source → the wrapped check is **skipped + flagged EXT**, never scored (M3 §14 R-c) | conditional-on-deal rows; refusal-gated checks; EXT sub-elements |
| `forbidden_phrase` | **(NEW — Gate-2 G8)** configured phrases must NOT appear (optionally in a context/outcome); **HARD** by default. Surfaces the existing generic `check_forbidden` (evaluator.py:80) as a rubric primitive | "no дочуване on refusal" (HARD, refusal-gated), забранено phrasings |
| `composite` | **(NEW — Gate-2 G7)** all-of a configured element list (each element itself a primitive) must be present | crit 7 device = model (`phrase_present`) + lease&cash (`numeric_structure`) + characteristic (`phrase_present`) |
| `opening_density` | **(NEW — Gate-2 G16)** ≥`min_words` in the first `n` seconds of the agent channel; surfaces `first_seconds_engagement` (evaluator.py:94). DET | first_seconds (B13) |
| `phrase_present` + `conditional_on:consent` | (mapping, Gate-2 G7) | **crit 10** ask-to-send-device, **crit 11** offer-new-service (both consent-gated) |
Feasibility classes (DET / DET-MAP / CMD / EXT) from M3 §14 carry over — they are properties of the
primitive+signal, not of A1. Note the split above: `deal_detect`, `path_select`, and the objection-match
half of `state_machine` are **CMD** (require the customer channel + the M3 §14 runtime change).

---

## 5. Engine changes required (generic, one-time)
- **E-1 Profile is required input, selected via `inputs.profile` (path).** Remove the A1 defaults at
  runner.py:278, 302 AND the A1 `call_path`/`contract_path` from the **workflow phase config**
  (workflows/callcenter-qa.json:15, B12) — the classify/evaluate phases read `run.context.profile`, not a
  hardcoded contract path. Selection mechanism = the `inputs.profile` run input (Gate-2 G12), which the
  runner loads once and puts on `run.context`; no filename magic, no A1 fallback anywhere.
- **E-2 Agent-channel detection reads markers from the profile.** `pick_agent_channel(texts, markers)` —
  markers from `profile.agent_markers` (B1 out of redact.py).
- **E-3 Redaction recognizers + recognizer SET parameterized by the language pack.** Vocabulary
  (B2-B4, B3b: number-words / connector / cues / labels) AND the **locale recognizer set** (B8 ЕГН
  checksum, B9 IBAN country prefix) come from `languages/<lang>.json`; universal recognizers (Luhn/email/
  digit-run) always on. Algorithms unchanged; which locale recognizers run + their params is config.
- **E-4 STT model AND language code from the language pack** (B5 model + **B7 language** — the runner
  must pass `language` to `transcribe_words`, stt.py:21/30; today it never does → BG hardwired).
- **E-5 The evaluate phase becomes the generic rubric-interpreter** — dispatch over `rubric[].primitive`,
  scoping each check by `applies_to_paths`; emit the per-criterion checklist + tiers (M3 §0). Replaces the
  A1-shaped single-score path. **The persistence check reads `profile.offer_category_id`** (B10), not the
  hardcoded `"offer1_discount"` (evaluator.py:131).
- **E-6 classify becomes `path_select`-driven** from `profile.call_paths` (replaces the static
  `call_path` default at runner.py:302). **Also re-home the classify phase's channel-ID keywords**
  (Gate-3 #6a): today it derives the agent/customer channel from `contract.categories_detail[].keywords`
  (runner.py:280-299) — that keyword source must come from the profile (e.g. `profile.agent_markers` or a
  `channel_id_keywords` field), or retiring `categories_detail` strands channel detection.
- **E-10 Command-mode judge prompt built from the profile rubric** (Gate-3 #6b — critical): today
  `judge_prompt` is assembled from `contract.categories_detail` (prompts.py:41-42). **Every CMD check**
  (`deal_detect`, `path_select` gating, `judge_check` objection-match) runs in command mode, so the judge
  prompt MUST be rebuilt from `profile.rubric` (the CMD-classed entries), not `categories_detail`. Without
  this the entire CMD half is unbuildable after the contract is retired.
- **E-11 Single-channel (mono / 3+ch) CMD disposition = INDETERMINATE, not silent "no deal"** (Gate-3 #2):
  on mono there is NO customer channel (`customer_text=""`, runner.py:331), so `deal_detect`/`path_select`
  gating/`judge_check` have no input. They must resolve to **indeterminate → human review** (or HOLD the
  CMD-classed checks), NEVER silently score "no deal"/not-met. Added to the §11 fail-closed table.
- **E-7 `deal_detect` primitive wired** (Gate-1 G5): the evaluate phase runs `deal_detect` first (CMD;
  needs the customer channel per the M3 §14 runtime change) to produce the `deal`/`consent`/`refusal`
  state that `conditional_on` checks read. Without it every conditional-gated check is inert. **The
  classify phase also needs the customer channel** for `path_select` (Gate-2 G13a) — both phases get
  `customer_text`, not just evaluate.
- **E-8 Redaction map into the evaluator** (Gate-2 G14; M3 §14 prerequisite): pass the redaction map to
  `evaluate()`/`evaluate_command()` so `slot_present` (DET-MAP, crit 1 / G6) works. Owned here as an arch
  task, not deferred.
- **E-9 Config-safety = FAIL-CLOSED (Gate-2 G3/G4/G5/G6/G9; consolidated in §11).** Load+validate the
  profile and language pack up front; any of {missing/invalid/partial profile, missing/partial language
  pack, `schema_version` mismatch, unknown `primitive` type, rubric ref to an unknown `applies_to_paths`
  id, `variants_ref` pointing nowhere, empty rubric} → **HOLD** (never silently skip/score), matching the
  harness's existing fail-closed posture (NER-absent → HOLD, runner.py:151).

---

## 6. The "A1-specific logic" I worried about, expressed as DATA (proof it dissolves)
- **Offer1→offer2→offer3 state machine** → `state_machine` primitive + transitions in `profile.rubric`.
  Client #2's different flow = different transitions in THEIR JSON; same engine.
- **Titular / non-titular gating** → `path_select` + `phrase_present` gating in `profile.call_paths`.
- **Mobile vs fixed required params** → `profile.service_branches`; engine checks "configured params present".
- **5 legal variants** → `variant_select` over `profile.legal_variants`; count/selectors are data.
None of these is A1 code once the primitives exist.

---

## 7. Proof-of-hollowness (the convergence acceptance)
Deliverable of the follow-on build (named here so the plan targets it):
- **T1 new-CLIENT:** a throwaway `profiles/demo-mock.json` (different markers, 2-item rubric, one
  call-path) runs end-to-end through the SAME engine with **zero code change**, producing a per-criterion
  checklist for its own rubric.
- **T2 new-LOCALE (Gate-1 G2):** a throwaway `languages/xx.json` client runs without triggering the ЕГН
  checksum / BG-IBAN prefix / `language="bg"` — proving B7/B8/B9 are config, not code.
- **T3 grep gate:** `grep -rP "[\x{0400}-\x{04FF}]" src/` and a scan for hardcoded ids/paths find **no**
  client/locale literal — B1, B3b, B6, B7, B8, B9, B10 gone from code; B11/B12 gone from `contracts/` and
  the workflow (B2-B4 vocab moved to the pack).
- **T4 config-safety (Gate-2 G15):** each fail-closed case in §11 (bad/missing profile, bad/missing pack,
  version mismatch, unknown primitive, dangling `applies_to_paths`/`variants_ref`, empty rubric) → the run
  **HOLDs** (asserted, not silently scored).
- **T5 A1-migration:** `profiles/a1.json` (folded from the retired contract + M3) runs the real A1 tenant
  end-to-end with the same checklist coverage as before the migration.
Until T1–T5 pass, "hollow" is unproven.

---

## 8. Re-frame of the M3 calibration spec (relationship)
`docs/m3-calibration-spec.md` stays valid as the **A1 requirements** (what to check, tiers, paths, legal
variants, feasibility classes). This architecture changes the **build**: from "write E1–E8 functions" to
"implement the §4 primitives once + author `profiles/a1.json` + `languages/bg.json`". Every M3 E-item and
criterion now has a primitive home (§4 table). The M3 §14 feasibility classes (DET/DET-MAP/CMD/EXT) and
the runtime prerequisite (pass redaction map + customer text) are unchanged and still required.

**Profile ↔ contract relationship (Gate-2 G1 — the profile ABSORBS the contract):** the per-client
`profiles/<client>.json` is the **single** client artifact. The current `contracts/callcenter-newplan-
esign.json` fields (B11: `categories_detail, ordering, ask_for_decision_phrases, objection_cues,
prosody_thresholds, first_seconds, forbidden_words, required_phrasings`) become sub-structures of the
profile's rubric/thresholds. `contracts/*.json` as a separate format is **retired** — not coexisting.
**A1 migration (Gate-2 G10 — the real-tenant deliverable, distinct from the throwaway demo):** author
`profiles/a1.json` by mechanically folding the existing A1 contract + the M3 additions into the profile
schema, and repoint `workflows/callcenter-qa.json` at `inputs.profile`. The T1 demo proves *hollowness*;
the A1 migration proves the *shipped tenant* still runs — both are required to close the build.

---

## 11. Config safety — fail-closed contract (Gate-2 G3/G4/G5/G6/G9)
The hollow interpreter's whole risk surface is malformed per-client JSON. Every case below is validated
**up front** (before any phase scores) and resolves to **HOLD** (never silent skip or score), consistent
with the harness's existing fail-closed posture (NER-absent → HOLD, runner.py:151-152):
| Case | Trigger | Behavior |
|---|---|---|
| Missing/unreadable profile | `inputs.profile` absent or unparseable | HOLD "profile missing/invalid" |
| Partial profile | required keys absent (`schema_version, client_key, language, rubric, call_paths`) | HOLD, name the missing key |
| Schema-version mismatch | `profile.schema_version` / pack version unsupported by the engine | HOLD "unsupported schema_version" |
| Missing/partial language pack | `languages/<language>.json` absent or missing number-words/recognizer toggles | HOLD |
| Unknown primitive | a `rubric[].primitive` the engine doesn't implement | HOLD (never skip — this is the central zero-code-change failure mode) |
| Dangling ref | `applies_to_paths` id not in `call_paths`; `variants_ref` not in `legal_variants` | HOLD |
| Empty set | rubric with zero checks; a `call_path` with zero bound checks | HOLD |
| **No customer channel** (mono / 3+ch input) | CMD-classed checks (`deal_detect`, gating, `judge_check`) have no customer input | CMD checks → **INDETERMINATE / human review**, never silently scored (Gate-3 #2) |
Validation is a distinct pre-flight step (not per-phase) so a bad profile never partially scores.

## 9. Open decisions (for Kamen — not decided here)
- **Open-D1 (dispatch):** keep the fixed `if/elif` phase dispatch (recommended — multi-tenancy comes from
  data, not pluggable phases; matches our earlier "registry not worth it" finding), OR generalize to a
  registry for fully MAWF-style hollow phases (larger, separable). Which?
- **Open-D2 (cue ownership):** some PII cues are pure language ("телефон") vs light-domain ("абонатен",
  "клиентски номер"). Split: language pack = pure-locale cues; profile may ADD domain cues. Confirm.
- **Open-D3 (prosody):** are prosody thresholds per-client (recommended — "confident delivery" is a
  client bar) or per-language? 
- **Open-D4 (run mode) — RESOLVED 2026-07-11: COMMAND MODE (the local AI judge grades every call).**
  Every PII-free call runs through the offline judge (Ollama, already provisioned this session). This
  makes the whole CMD class (`deal_detect`, `path_select` gating, `judge_check` objection-match) buildable;
  cost is ~30s/call + the judge must be running. The deterministic DET checks still run cheaply alongside;
  command mode adds the judgment layer on top.
- **Open-D5 (locale recognizer set):** confirm the language pack declares which recognizers run (ЕГН +
  IBAN-prefix per-locale; Luhn/email/digit-run universal) — i.e. the pack is a `{vocab + recognizer
  toggles + params}` bundle, not just word lists. (Follows from Gate-1 G2.)
- **Open-D6 (name-slot granularity — Gate-3 #1):** `slot_present` for crit-1 "name said" can't distinguish
  name from address/org at the current map granularity (all → `GLINER_PII`). Choose: **(a)** enrich the
  redaction map to carry the GLiNER per-label (name vs address) so the slot is precise — small redact.py
  change, keeps the map value-free; or **(b)** accept the coarse "a PII slot in the intro region" proxy
  and downgrade crit-1's exactness. Recommend (a).

## 10. Out of scope
No profile-authoring UI; no change to the DSP algorithms; BG language pack only initially (schema
supports more); the M3 evaluator-logic BUILD itself (this pass designs the architecture the build targets).
