# Implementation plan — human-readable scorecard (report-model + renderer + new criteria)

**Rests on:** `docs/research/scorecard-human-structure-research.md` (hardened through 3 gates). Decisions
locked there: **D1** = JSON report-model + thin renderer; **D4** = renderer + new rubric criteria.
**Objective:** produce a team-leader-readable scorecard from the existing evaluation, and surface the
client-watched behaviors the rubric doesn't yet score. **Engine stays hollow** (all Bulgarian labels/prose
in JSON config; `src/` generic). **commit_policy = none.**

## Current-state facts (grounded)
- `run.context["evaluation"] = {mode, contract_key, checklist[], violations[], advisories[], review_needed[], intonation}` — assembled in `runner.py:_emit_checklist` (runner.py:441-455).
- checklist rows: `{id, primitive, tier, applies_to_paths, status∈{met,not_met,indeterminate,na}, evidence}` (`rubric.py:_row`).
- duration lives in `ctx["ingest"].duration_seconds`; path in the `path` checklist row / `ctx["classify"]`; deal in the `deal` row evidence `{deal, logistics, ...}`.
- disposition signals: `run.status` (`skipped`/`blocked`), `ctx["ingest"].skipped`, `evaluation.held`.
- `evaluator.persistence()` (evaluator.py:109-121) already computes `offer_repeats`, `ask_for_decision_count`, `persistence_flag` — a signal that exists but is not a checklist criterion.

## Slice A — Report model + renderer (the D1 core)

**A1. `src/cc_harness/report/__init__.py` + `src/cc_harness/report/model.py`** (NEW, generic — no literals):
`build_report_model(context, presentation, status_labels) -> dict`. Pure function. Produces:
```
{ header:{call_id, duration_mmss, path, disposition, outcome:{deal, reason, confidence}},
  summary:{hard_total, hard_met, hard_violations, hard_review, advisories},   # per §4.A counting rule
  sections:[{id, title, rows:[{label, status, status_kind, evidence, proxy_note}]}],
  coaching:[str] }
```
- Counting rule (research §4.A, exact): `hard_total` = HARD rows with status≠na; `hard_met`=HARD met;
  `hard_violations`=HARD not_met; `hard_review`=HARD indeterminate; `advisories`= SOFT rows rendered ⚠️
  (soft not_met OR soft indeterminate OR a tone-override — see A-note). Assert met+viol+review==hard_total.
- Grouping/labels/proxy_note come from `presentation` (per-criterion), NOT hardcoded.
- disposition: skipped→"Пропуснато обаждане"(+reason); blocked/held→"Задържан за преглед"(+reason);
  else "Оценен". Held/skipped → header only, `sections=[]`.
- outcome: from the `deal` row evidence; `confidence="heuristic"` when it fired via logistics/number signal.
- coaching: rule-based (generic) — list HARD violations' labels, then the weakest SOFT dimension(s);
  templates (BG) come from `presentation.coaching`, filled generically.

**A2. `src/cc_harness/report/render_text.py`** (NEW, generic): `render_text(model, status_labels) -> str`
— the box layout from research §6. Icons/words from `status_labels`. No literals.

**A3. Presentation config — `profiles/a1.json` add `scorecard_presentation`:**
```
{ "sections":[{"id":"nachalo","title":"Начало и съгласие","order":1}, ... ],
  "criteria":{ "identify_a1":{"label":"Представи се от името на А1","section":"nachalo",
                              "proxy_note":"по ключова дума"}, ... every rubric id ... },
  "coaching":{ "sale":"...", "no_sale":"...", "weak_listening":"...", ... } }
```
BG lives here (hollow-safe: config, not `src/`). Labels are the §5 honesty-corrected ones.

**A4. Status labels — `languages/bg.json` add `status_labels`:**
`{ "met":{"icon":"✅","word":"Изпълнено"}, "violation":{"icon":"❌","word":"Нарушение"},
   "review":{"icon":"🔍","word":"За преглед"}, "na":{"icon":"➖","word":"Неприложимо"},
   "advisory":{"icon":"⚠️","word":"Препоръка"} }`. Locale-generic BG (fail-closed string per M2 pattern).

**A5. `config/loader.py`:** parse `scorecard_presentation` (Profile) + `status_labels` (Lang), fail-closed
if malformed (dict expected). Optional (absent → renderer falls back to raw ids, no crash).

**A6. `scripts/scorecard.py`:** default = human view (`build_report_model`+`render_text`); `--verbose`
keeps today's raw checklist (D2). Streaming/hold-report behavior preserved.

**A7. Tests — `scripts/test_report_model.py` (NEW):** fixture mirroring Ана v3 →
assert grouping into sections; counts `hard 10/11, 0 viol, 1 review, 4 advisories`; disposition "Оценен";
outcome deal+heuristic; held/skipped fixtures → sections empty + disposition text; render_text smoke +
no-Cyrillic-in-src (hollow gate covers it).

## Slice B — New rubric criteria (D4), grounded in CallScript.docx

Add to `profiles/a1.json.rubric` + a `scorecard_presentation.criteria` label each. Only criteria that fit
EXISTING primitives or the already-computed persistence signal — each with a `_note` marking it
CALIBRATION-PENDING (phrases seeded from the script, to be tuned on labelled calls):
- **B1 `ask_for_decision`** (soft, `phrase_present`) — phrases = contract `ask_for_decision_phrases`
  (да запишем/да продължим/съгласни ли сте/потвърждавате/да активираме/искате ли). Surfaces «не искат решение».
- **B2 `praise_benefits`** (soft, `phrase_present`) — phrases seeded from the script's benefit language
  (по-бърз интернет / повече канали / спестявате / богат избор / по-добро качество / на разположение).
  Surfaces «не хвалят / не дават практически ползи».
- **B3 `titular_check`** (hard, `phrase_present`, `applies_to_paths:[non_titular_yes,non_titular_no]`) —
  phrases (вземате решение / Вие ли сте титуляр / титуляр ли сте). Surfaces the non-titular gating question.

**Staged (NOT in this slice — need NEW primitives + calibration; recorded, not silently dropped):**
- `offer_repeat` (≥2 offer statements) — needs a counting primitive; the `persistence()` signal exists but
  isn't a rubric primitive. Follow-on: add a `phrase_count`/`min_count` primitive.
- Offer-2/3 escalation discipline (present offer-2 only after rebuttal; ≤2 rebuttals; never close with
  «дочуване» on refusal) — a state machine (m3 §4); its own research+calibration slice.

## Verification
- Fast: `scripts/test_hollow_grep.py` (no Cyrillic in `src/`), full `scripts/test_*.py`, new report tests.
- Real-data render: build the report-model from a persisted Ана command-run state (`.cc-harness-state/`)
  or a fixture built from the v3 checklist, and eyeball the rendered box.
- Slice B: confirm the 3 new criteria appear as rows with grounded evidence and don't flip existing
  hard-violation counts on the Ана call (they're soft except titular_check which is `na` on titular).

## Out of scope / not done here (explicit)
- Live calibration of B1-B3 phrase lists against a labelled set (needs Kamen's labelled calls).
- offer_repeat + escalation state machine (staged above).
- HTML/JSON-file emission surface (D1 renderer is text first; JSON model is the reusable layer).
