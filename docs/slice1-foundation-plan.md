# Slice 1 — Foundation: make the harness hollow (config-driven, per-client JSON)

**Objective:** the harness reads a per-client **profile** + a per-language **pack** instead of A1 being
hardcoded; missing/broken config **fails closed (HOLD)**; proven by a throwaway 2nd profile that runs with
**zero code change** and by **A1 output parity**. Grounded in `docs/multi-tenant-architecture.md` (3 gates +
confirmatory PASS). **Run mode decided:** command mode (AI judge) — but that is Slice 2+; Slice 1 does NOT
touch scoring behavior.

**Locked decision (P2): Slice 1 is BEHAVIOR-PRESERVING for A1.** The profile ABSORBS the current contract;
the existing `evaluate()`/redaction/prosody run **unchanged**, just fed their constants from config. The
rubric-interpreter, the ~10 new primitives, and the AI-judge checks are **later slices**. This keeps Slice 1
a pure plumbing change with a hard acceptance bar: **identical output to today on the A1 sample.**

## Scope — files changed (granular; each with reason)
1. **NEW `profiles/a1.json`** — `{schema_version, client_key:"a1", language:"bg", agent_markers:[…B1…],
   offer_category_id:"offer1_discount", contract:{…the entire current contract JSON, absorbed…}}`.
   *(migrates B1, B6, B10, B11)*
2. **NEW `languages/bg.json`** — `{schema_version, number_words:[…B3…], number_connector:"и",
   context_lead_ins:[…B2…], ner_labels:[…B4…], stt_model:"faster-whisper-small", stt_language:"bg",
   recognizers:{egn:true, iban_prefix:"BG"}}`. *(migrates B2,B3,B3b,B4,B5,B7,B8,B9)*
3. **NEW `src/cc_harness/config/loader.py`** — `load_profile(path) -> Profile`, `load_language(key) -> Lang`.
   Fail-closed: missing/unreadable/partial/`schema_version` mismatch → raise `ConfigError`. Frozen dataclasses
   `Profile{schema_version,client_key,language,agent_markers,offer_category_id,contract}` and
   `Lang{number_words,number_connector,context_lead_ins,ner_labels,stt_model,stt_language,egn,iban_prefix}`.
   *(E-1, E-9, §11 for the Slice-1 keys)*
4. **`redact.py`** — parameterize the hardcoded constants (keep algorithms):
   - `pick_agent_channel(texts, markers)` — markers arg (was module `SCRIPT_MARKERS`).
   - `find_number_token_spans(text, number_words, connector, min_run=4)` — args.
   - `find_context_spans(text, lead_ins, follow_chars=40)` — arg.
   - `find_pattern_spans(text, iban_prefix, egn_enabled)` → `_classify_number` gated by `egn_enabled`;
     IBAN regex built from `iban_prefix`.
   - `detect_spans(text, ner_hook, include_context, lang)` — thread the lang config down.
   Module-level `SCRIPT_MARKERS/CONTEXT_LEAD_INS/BG_NUMBER_WORDS/_NUM_CONNECTOR/EGN_WEIGHTS(keep as pure
   helper)/IBAN literal` **removed as defaults** (EGN_WEIGHTS stays as a function constant used only when
   `egn_enabled`). *(E-2, E-3, B1,B2,B3,B3b,B8,B9)*
5. **`ner.py`** — `ner_spans(text, labels)`; labels arg (was `GLINER_LABELS`). *(B4)*
6. **`stt.py`** — caller passes `language`; `transcribe_words(path, language, model_dir)`. **Both** callers
   updated: redaction phase (runner.py:163) AND transcription phase (runner.py:233) pass
   `language=lang.stt_language`. **stt_model resolution (verify-plan #12 parity fix):** `lang.stt_model` is a
   NAME; the loader resolves it to the full dir `~/.callcenter-harness/models/<name>` before it reaches
   `model_dir`, so A1 (`faster-whisper-small`) resolves to today's `DEFAULT_MODEL` path → byte-identical, no
   HOLD. *(E-4, B7)*
7. **`evaluator.py`** — `offer_category_id` threaded through **`gap_checks` AND both `evaluate` and
   `evaluate_command`** (verify-plan #10: `evaluate_command` also calls `gap_checks` at :330). `load_contract`
   gains a `from_dict` path (or the phases pass the absorbed `contract` **dict** directly, not a file path).
   *(E-5 partial, B10)*
8. **`runner.py`** —
   - `start()`: if `inputs.profile` present, `load_profile` + `load_language` (resolve `stt_model` to full
     path) and put `profile`/`lang` on `run.context`; on `ConfigError` → `run.status="blocked"`, return.
   - **Profile is PHASE-LEVEL required, not global (verify-plan #19 decision):** the `audio_redaction`,
     `call_path_classify`, `transcription`(for lang), `prosody`, `phase_ledger` phases HOLD if
     `run.context` has no profile/lang; `noop` and `ingest` do NOT require it. → `noop`/`ingest` smokes need
     no profile; audio/eval workflows do.
   - redaction phase: `pick_agent_channel(…, profile.agent_markers)`; `detect_spans(…, lang=lang)`; **rebind
     the NER hook with labels (verify-plan #8):** `ner_hook = lambda t: ner_mod.ner_spans(t, lang.ner_labels)`
     (was bare `ner_mod.ner_spans`, :153); `transcribe_words(…, language=lang.stt_language, model_dir=lang.stt_model)`.
   - **transcription phase (verify-plan #9, :233):** `transcribe_words(…, language=lang.stt_language,
     model_dir=lang.stt_model)` — was omitted; add `lang` threading here too.
   - classify phase: contract **dict** from `profile.contract` (remove the `or "contracts/…"` default, :278);
     `call_path` from `profile`/config (remove the `"newplan_esign"` default, :302). Channel-ID keyword
     scoring stays on `profile.contract.categories_detail` (unchanged for A1; re-homing is a later slice —
     verify-plan #21).
   - **classify→phase_ledger handoff (verify-plan #18):** replace the path-string plumbing
     (`run.context["evaluation_contract_path"]`, :308/316) with the **contract dict on `run.context`**;
     phase_ledger reads the dict, not a re-read file.
   - phase_ledger phase: contract dict from context; `evaluate(..., offer_category_id=profile.offer_category_id)`
     and `evaluate_command(..., offer_category_id=…)`.
   *(E-1, B6, B10, B12)*
9. **`workflows/callcenter-qa.json`** — remove `call_path`/`contract_path` from the classify phase; the run
   supplies `inputs.profile`. *(B12)*
10. **RETIRE `contracts/callcenter-newplan-esign.json`** — its content now lives inside `profiles/a1.json`
    (`contract` sub-object). Delete the standalone file after A1-parity passes. *(§8)*
11. **NEW `profiles/demo-mock.json` + `languages/xx.json`** — throwaway 2nd tenant (2 marker words, the
    absorbed contract reduced to 2 mandatory categories, a minimal Latin-ish language pack) to prove
    hollowness. Kept in-repo as a fixture. *(§7 T1/T2)*
11b. **Update every existing caller of the re-parameterized functions (verify-plan #2/#6/#7/#11 — the main
   break risk):**
   - `scripts/test_recall_checks.py` — calls `find_number_token_spans(text)` ×8 and `detect_spans(txt, …)`
     ×1; update to pass the bg number-words/connector/lang (import from `languages/bg.json` via the loader,
     or a test helper).
   - Smoke scripts that call `.start()` on an audio/eval workflow must pass `inputs={"profile":"profiles/a1.json", …}`:
     `cc_pipeline_smoke.py`, `cc_eval_smoke.py`, `cc_command_eval_smoke.py`, `scrub_and_retire.py`,
     `cc_redact_smoke.py` (already noted). **No change needed** for `cc_smoke.py`(noop), `cc_ingest_smoke.py`
     (ingest), `test_engine_upgrades.py`(noop) — phase-level rule (item 8) exempts them.
   - `docs/m3-calibration-spec.md:5` stale pointer to the retired contract → repoint to `profiles/a1.json`
     (verify-plan #17; doc-only).
12. **Tests:**
    - `scripts/test_config_safety.py` — missing / unreadable / partial (missing required key) / bad
      `schema_version` profile AND language pack each → `ConfigError` (→ HOLD). *(§11 T4)*
    - `scripts/test_hollow_grep.py` — `grep -rP "[Ѐ-ӿ]" src` finds **nothing**; no `contracts/…`
      / `offer1_discount` / `newplan_esign` literal in `src`. *(§7 T3)*
    - `scripts/test_profile_parity.py` (real-audio smoke): `profiles/a1.json` reproduces the pre-change
      redaction (same masked-span count/categories on the 94s sample) AND the same deterministic
      adherence output. *(§7 T5)*
    - demo-profile smoke: `profiles/demo-mock.json` runs `redact`/`callcenter-qa` end-to-end with zero code
      change, producing a valid (different) result. *(§7 T1)*

## Out of scope (later slices — named, not built)
Rubric-interpreter + the ~10 new primitives (Slice 2); the AI-judge CMD checks / judge-prompt-from-rubric /
customer-channel plumbing / redaction-map-into-evaluator / mono disposition (Slice 3, per Open-D4=command);
call-path taxonomy + legal variants + M3 criteria beyond today's (Slice 2-3). Slice 1 changes NO scoring.

## Verification (P1 — build without coming back)
`PYTHONPATH=src python scripts/test_config_safety.py` → all HOLD; `…/test_hollow_grep.py` → clean;
`…/test_profile_parity.py <a1 sample>` → parity PASS; demo smoke → completes; existing suites
(recall/chunker/gap/tone/engine) still green; air-gapped redact smoke via `profiles/a1.json` → 6 spans.

## Open (P2 — genuine, surfaced not buried)
- **Adopting Open-D1/D2/D3/D5/D6 defaults** (dispatch=if/elif, cues=pack+profile-extras, prosody=per-client,
  recognizer-set=pack, name-slot=enrich-map). Slice 1 only needs D5 (pack recognizer toggles) — adopted as
  the recommended default. The rest bind in later slices.
