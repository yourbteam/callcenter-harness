# Slice 2 — Generic rubric-interpreter + deterministic check primitives + checklist output

**Objective:** the evaluate phase becomes a GENERIC rubric-interpreter over `profile.rubric[]`; the DET +
DET-MAP check primitives are implemented once; A1's rubric expresses its DET/DET-MAP M3 criteria; the
output becomes the **per-criterion checklist + two-tier severity** (the M3 reframe), replacing the single
`adherence_score`. Grounded in `docs/multi-tenant-architecture.md` §4/§14 + `docs/m3-calibration-spec.md`.
Slice 1 (config-driven engine, eee9ffe) is the foundation.

**Locked scope boundary (P2):** Slice 2 is **DET + DET-MAP only**. The CMD / AI-judge primitives
(`deal_detect`, `path_select` gating, `judge_check` objection-match, judge-prompt-from-rubric) and the
customer-channel plumbing are **Slice 3**, gated on tomorrow's deal/no-deal/refusal audio. Run mode is
already decided = command mode, but that's exercised in Slice 3.

## Design decisions (locked)
- **D1 — Rubric-interpreter replaces the single-score path.** The `phase_ledger` deterministic mode runs
  the interpreter over `profile.rubric`; the old `evaluate()` scalar `adherence_score` headline is retired.
  Output `run.context["evaluation"]` (deterministic) = `{mode:"deterministic", checklist:[{id, primitive,
  tier, status ∈ {met,not_met,indeterminate,na}, applies_to_paths, evidence}], violations:[hard & not_met],
  advisories:[soft signals], review_needed:[indeterminate rows] (F11 — INDETERMINATE gets a visible
  rollup, M3 §14 R-d), intonation:{…} (F7 — the M2 prosody dimension is PRESERVED, not dropped)}`. No
  aggregate pass/fail (M3 §0). `evaluate_command` (CMD) untouched — Slice 3.
- **D1a — Consumer update (F6/F10, REQUIRED):** `scripts/cc_eval_smoke.py` currently asserts
  `adherence_score`/`mandatory_count`/`matched_mandatory`/`category_status` on the deterministic run
  (cc_eval_smoke.py:44-62). Those are the retired scalar → **update the smoke** to assert the new
  `checklist`/`violations`/`advisories`/`review_needed`/`intonation` shape. (Verification below is corrected:
  all Slice-1 suites stay green EXCEPT this smoke, which is intentionally rewritten to the reframed shape.)
- **D2 — Primitive bodies: reuse where clean, NEW where the shipped check doesn't fit (F1/F2).** CLEAN
  reuse: `phrase_present`←`_find_quote`/`check_required_phrasings` (note the latter returns the *missing*
  list — invert); `opening_density`←`first_seconds_engagement`; `forbidden_phrase`←`check_forbidden`
  (simple presence, HARD). **NEW logic** (not drop-ins): `phrase_ordering` — pairwise `{before_phrases,
  after_phrases}`, built on `_first_offset` (NOT `check_ordering`, which is category-keyed); `word_avoid`
  and `word_prefer` — COUNT-based (§6 is count-weighted) with `except_in_mandated_spans` exclusion (D4);
  `numeric_structure`, `composite`, `slot_present`, `conditional_on` — new (evaluator §4).
- **D3 — Runtime prereq + `slot_present` bridge (F4/F5).** Feed the **redaction map**
  (`run.context["redaction"]["redaction_map"]`, entries `{start,end,category,channel}` — time-ranges, no
  char region) into phase_ledger (M3 §14 E-8). `slot_present` for **crit-1 name-slot** (Slice 2): find the
  intro region as a TIME window (first N s), assert a name-category span (`NER_*`/`GLINER_PII`/`MULTI` —
  F5c: MULTI may contain a name) on the AGENT channel overlaps it. The **char-offset→time bridge** (map a
  phrase's char offset in `source_text` → time via `agent_words`) is specified for the "after phrase X"
  variant. **G6 courier-capture is CUSTOMER-side (F5a) → deferred to Slice 3** (customer channel). So
  Slice-2 `slot_present` covers crit-1 name-slot only.
- **D4 — `word_avoid` mandated-span precedence (M3 §6 G15):** avoid-word hits INSIDE mandated spans (legal
  verbatim / scripted rebuttals declared in the rubric) are not penalized. Slice-2 impl: a `word_avoid`
  check takes an optional `mandated_regions` (phrase list); hits within a window of a mandated phrase are
  excluded.
- **D5 — `conditional_on` in Slice 2:** the wrapper's condition source (deal/consent/refusal) comes from
  `deal_detect`, which is **Slice 3**. In Slice 2 a `conditional_on` check whose condition is unresolved
  returns **`indeterminate`** (never met/not_met) — honest, not a silent pass.
- **D6 — CMD entries deferred:** A1's Slice-2 rubric authors ONLY DET/DET-MAP checks. CMD checks
  (deal/gating/objection-match) are added to the rubric in Slice 3. The interpreter, if it meets a
  primitive it doesn't implement yet, returns `indeterminate` with `reason=deferred` (NOT a HOLD — the
  DET checks still score); those rows show up in `review_needed`.
- **D7 — rubric vs contract authority (F9, dual-source reconciliation):** `profile.contract.categories_
  detail` STAYS (the classify phase derives channel-ID keywords from it, runner.py:320 — unchanged this
  slice). The **`rubric` is authoritative for SCORING**; `categories_detail` is only the channel-ID keyword
  source. A1's rubric phrases may reuse the same keyword lists — a **known transient overlap**, resolved
  when classify keywords move to the profile (later slice). Documented, not silently duplicated.

## Files
1. **NEW `src/cc_harness/phase_ledger/primitives.py`** — one handler per primitive; each takes
   `(check_cfg, ctx)` where `ctx = {source_text, agent_words, redaction_map, mandated_regions, lang}` and
   returns `{status, evidence}`. Registry `PRIMITIVES = {"phrase_present": ..., ...}`. Unknown primitive →
   `indeterminate(reason="deferred")`.
2. **NEW `src/cc_harness/phase_ledger/rubric.py`** — `run_rubric(rubric, ctx) -> checklist` + derive
   `violations`/`advisories`; validate each check has a known-or-deferred primitive + a tier.
3. **`evaluator.py`** — keep the pure `check_*` helpers (primitive bodies); the single-score `evaluate()`
   is superseded by the rubric path (leave it importable for now, unused by the phase).
4. **`runner.py` phase_ledger phase** — deterministic branch calls `run_rubric` with the redaction map +
   agent transcript; emit `checklist`/`violations`/`advisories` in `run.context["evaluation"]`.
5. **`config/loader.py`** — extend the frozen `Profile` with optional `rubric`, `call_paths`,
   `service_branches`, `legal_variants` using `field(default_factory=list/dict)` (F8 — mutable defaults on a
   frozen dataclass need default_factory; `field` is already imported). Validate: each `rubric[]` entry has
   `id`, `primitive`, `tier ∈ {hard,soft}`; `applies_to_paths` optional (default all). Fail-closed on a
   rubric entry missing `id`/`primitive`/`tier` (M3 §11).
5b. **`scripts/cc_eval_smoke.py`** — rewrite the deterministic assertions to the checklist shape (D1a).
6. **`profiles/a1.json`** — author `rubric[]` for A1's DET/DET-MAP criteria (representation+A1, record
   consent, price-structure, device composite, right-of-withdrawal, detailed summary, thank-you, ordering,
   words prefer/avoid, opening density, name-slot DET-MAP, courier-capture DET-MAP). `call_paths`/
   `legal_variants` DATA may be authored now (consumed in Slice 3).
7. **Tests:**
   - `scripts/test_primitives.py` — each DET primitive on synthetic text (met/not_met/indeterminate);
     `word_avoid` precedence (hit in a mandated span not penalized); `numeric_structure on_masked`;
     `slot_present` given a synthetic redaction map; `conditional_on` unresolved → indeterminate;
     unknown primitive → deferred-indeterminate.
   - `scripts/test_rubric.py` — `run_rubric` over a small rubric → checklist + violations/advisories;
     tier + applies_to_paths honored; a malformed rubric entry → ConfigError (via loader).
   - `scripts/test_a1_checklist.py` (real audio) — the A1 rubric over the 94s sample produces a checklist
     with the expected DET criteria firing (representation, price, right-of-withdrawal present; etc.);
     **no crash**, output shape = checklist (not a scalar score).

## Verification (P1) — corrected (F6/F10)
`test_primitives`/`test_rubric` (fast) green; `test_a1_checklist` on the sample → sane checklist (correct
shape, DET criteria fire, no crash); hollow-grep still green (rubric is DATA in `profiles/a1.json`);
config-safety extends to a malformed rubric entry. **All Slice-1 suites stay green EXCEPT
`cc_eval_smoke.py`, which is intentionally rewritten** to the reframed checklist shape (D1a) — this is the
one deliberate behavioral change (the M3 reframe), not a regression.

## Out of scope (Slice 3, needs audio)
`deal_detect`, `path_select` gating, `judge_check` objection-match, judge-prompt-from-rubric, customer-
channel plumbing (incl. **G6 courier-capture slot_present** — customer-side, F5a), **offer-2/3
transition-marker sequencing** (§8 probabilistic + needs the offer state machine, F12), mono
CMD-indeterminate disposition, legal-variant mask-aware closeness verification.

## Open (P2)
- The exact A1 rubric wording (which phrases per criterion) is authored from the script; where a phrase set
  is uncertain it's marked in the profile and validated against tomorrow's audio in Slice 3.
