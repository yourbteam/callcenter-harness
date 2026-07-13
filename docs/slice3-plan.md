# Slice 3 (final) — CMD / AI-judge check primitives on the rubric-interpreter

**Objective:** implement the command-mode (CMD / AI-judge) checks on top of the Slice-2 rubric-interpreter,
so the checklist gains the judgment-heavy criteria: deal-vs-no-deal, titular/non-titular path + gating,
objection-match effort, active-listening/emotion, courier-capture, offer-2/3 sequencing. Run mode =
command (offline Ollama judge, already provisioned). Grounded in docs/multi-tenant-architecture.md §4/§14 +
docs/m3-calibration-spec.md §14 CMD rows. Slices 1 (eee9ffe) + 2 (4b15eb2) committed.

## Current state (post-Slice-2, grounded)
- Command-mode `evaluate_command` (evaluator.py:263) runs a judge built from `contract.categories_detail`
  (prompts.py:36-58) that already returns per-element `conveyed`, `emotion`, `active_listening`, and
  `objection{raised,rebutted,evidence}` — then builds its OWN `adherence_score` ledger (the LEGACY shape).
- The Slice-2 rubric-interpreter runs only in the DETERMINISTIC branch; command mode does NOT yet emit the
  checklist. CMD primitives (deal_detect/path_select/judge_check) don't exist → `run_primitive` returns
  `indeterminate(deferred)`; `conditional_on:deal` defers.
- The runner command branch passes `source_text, prosody, customer_text, agent_words, duration,
  offer_category_id` to `evaluate_command` (runner.py:375-383). The redaction map is on
  `run.context["redaction"]["redaction_map"]` (per-channel).

## Design decisions (locked)
- **D1 — Unify command mode under the rubric-interpreter.** The command-mode phase_ledger branch runs the
  SAME `run_rubric` as deterministic, but first calls the judge ONCE and attaches its structured verdict to
  `ctx["judge"]`. DET primitives run unchanged (agent text). CMD primitives read `ctx["judge"]` / the
  customer channel. Output = the CHECKLIST (+ violations/advisories/review_needed + intonation) — same
  shape as Slice 2. The legacy `evaluate_command` adherence_score ledger is retired (as Slice 2 retired the
  deterministic scalar). `evaluate_command` is refactored to `judge_call(...) -> dict` (run judge, return
  structured verdict) — no scoring in it.
- **D2 — judge-prompt-from-rubric** (new `judge_prompt_from_rubric` in prompts.py): built from the
  profile.rubric entries whose primitive is CMD (`judge_check`/`deal_detect`/`path_select`), NOT
  `categories_detail`. For each CMD check it emits `{id, question}`; asks the judge to return a verdict per
  id + `deal{happened,consent,refusal}` + `path{decision_maker}` + emotion + active_listening + objection.
  Keep the `PHASE CONTRACT:`/`SOURCE REQUEST:`/`OUTPUT JSON SHAPE:` markers for fixture parsing.
- **D3 — Resolver-first interpreter pass.** `run_rubric` (command mode) runs the `deal_detect`/`path_select`
  entries FIRST (regardless of their position in the rubric list), writes `ctx["deal"]`/`ctx["consent"]`/
  `ctx["path"]`, THEN runs the remaining checks so `conditional_on`/`applies_to_paths` resolve against real
  state. The resolver entries are ALSO emitted as checklist rows (their status visible), but executed only
  ONCE (verify-plan #3 — the second pass skips already-resolved resolver ids, no double-execution).
- **D4 — CMD primitives** (primitives.py; read `ctx["judge"]`/customer channel — absent in deterministic
  mode → they return `indeterminate` there, exactly Slice-2 behavior, so deterministic runs are unchanged):
  - `deal_detect` → {deal,no_deal,refusal} from `ctx["judge"]["deal"]` + customer consent/address markers.
  - `path_select` → titular vs non_titular (gating question in customer channel + judge) + mobile/fixed
    service branch (agent-side cue word, DET-detectable); writes `ctx["path"]`.
  - `judge_check` → reads `ctx["judge"][id]` (objection-match, active_listening≥thr, emotion≥thr) → met/not_met.
- **D5 — conditional_on resolves** (primitives.py): `deal_detect` writes BOTH `ctx["deal"] ∈
  {deal,no_deal,refusal}` AND `ctx["consent"]: bool` (verify-plan #5 — consent had no home). `conditional_on`
  maps `condition` → the right ctx key: `deal`→`ctx["deal"]=="deal"`, `refusal`→`=="refusal"`,
  `consent`→`ctx["consent"]`. A gated check whose condition is false → `na` (not applicable). When the
  state is ABSENT (deterministic mode / no judge) → `indeterminate` (Slice-2 fallback; the existing
  `test_primitives` assertion stays green — it checks status only). **Implementation guardrail (#4): read
  `ctx.get("judge")`/`ctx.get("deal")`, never subscript — absent key must not KeyError.**
- **D6 — applies_to_paths filtering:** a checklist row whose `applies_to_paths` excludes `ctx["path"]` →
  `na`. (Slice-2 rows have empty applies_to_paths → apply to all.)
- **D7 — customer-channel + map plumbing:** the command ctx gains `customer_text`, `customer_words`, and
  the per-channel `redaction_map`; `slot_present` for **G6 courier-capture** reads a PHONE_OR_ID/address
  span on the CUSTOMER channel after the address-request phrase.
- **D8 — mono / no-customer-channel disposition (M3 §14 R-b):** if there is no customer channel, every CMD
  check → `indeterminate` (→ review_needed), NEVER a silent no_deal/not_met.
- **D9 — offer-2/3 sequencing (DET, §8):** a hard `phrase_ordering`/forbidden check — the offer-2 transition
  phrase (profile markers, script L25/L26/L27) must NOT be the first offer; if it appears before any offer-1
  discount phrase → violation.

## Files
1. `phase_ledger/prompts.py` — add `judge_prompt_from_rubric(rubric_cmd, source, customer, prosody)`.
2. `phase_ledger/evaluator.py` — refactor `evaluate_command` → `judge_call(...)` returning the raw judge
   verdict dict (no scoring); keep JSON parsing/repair. **Where the retired G8/NFR-5 invariants move
   (verify-plan #1):** the "met element must carry an exact SOURCE quote" check moves INTO `judge_check`
   (a judge verdict is `met` only if it includes an evidence substring that appears in the source); the old
   "omitted category → raise" becomes: a rubric CMD check with NO judge verdict → `not_met` (never a hard
   raise — a stingy judge must not crash the run).
3. `phase_ledger/primitives.py` — add `deal_detect`, `path_select`, `judge_check`; extend `conditional_on`
   to read `ctx["deal"]`; add offer-sequencing (D9) as a primitive or phrase_ordering config.
4. `phase_ledger/rubric.py` — resolver-first pass (D3) + applies_to_paths filtering (D6).
5. `engine/runner.py` — command branch: build customer ctx (text/words + per-channel map), call the judge
   once (rubric-derived prompt), run `run_rubric`, emit the checklist (retire the legacy command ledger).
6. `profiles/a1.json` — author CMD rubric entries (deal_detect, objection_match judge_check,
   active_listening, emotion, path gating, offer-sequencing, courier-capture) + `call_paths`
   (titular/non_titular) + `service_branches` (mobile/fixed) + `legal_variants`.
7. `scripts/fixture_role_command.py` — update the deterministic test judge to emit the NEW verdict shape
   (per-CMD-id verdicts + `deal{happened,consent,refusal}` + `path{decision_maker}` + emotion/active/
   objection), so the fast command path doesn't need Ollama (verify-plan #8).
8. Tests: `scripts/test_cmd_primitives.py` (fast — deal_detect/path_select/judge_check/conditional_on
   against a synthetic `ctx["judge"]`; mono→indeterminate; applies_to_paths filtering; consent condition);
   a judge-prompt builder test (rubric CMD entries → prompt has the ids/markers, no categories_detail);
   `cc_command_eval_smoke.py` rewritten to assert the checklist shape from the COMMAND branch (via the
   updated fixture — no Ollama needed for the smoke).

## Verification (P1)
Fast CMD-primitive + prompt-builder tests green (fixture judge, no Ollama). Command-mode checklist on a
real recording via the Ollama judge (Ollama up): checklist includes the CMD rows resolved (deal/path/
objection), intonation preserved, no legacy adherence_score. **Validation by-inspection against the 15
recordings in hand** — a give-up exemplar → objection_match not_met + no_deal; a deal/address-for-documents
call → deal + legal checks apply; the retention call → keep-conditions path. hollow-grep stays green (all
CMD logic generic; A1 markers/questions in the profile). All Slice-1/2 + prior suites green.

## Out of scope
Client OPEN items (MAX Sport/Xplore mandatory?, no-objection scoring, non-sales disposition) — rubric DATA
addable when the client answers; not engine work. New audio — not needed.

## Open (P2)
- The judge's determinism: the Ollama model may vary run-to-run; validation is by-inspection + the fixture
  path is deterministic for CI. Flagged, not resolved by more code.
