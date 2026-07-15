# Human-readable scorecard structure — research & design

**Status:** research findings, hardened through the three gates (doc-readiness, coverage, satisfaction).
NOT yet implemented — no code. Structure only.
**Objective:** define the STRUCTURE of the per-call QA scorecard so a non-technical reviewer (тим лидер)
can read one call's result and understand: *did the agent follow the mandatory script, did it end in a
sale, were they confident/warm, did they fight for the sale, and what exactly went wrong.*
**Audience:** call-center team leaders. **Language:** Bulgarian labels (NFR-1 — reporting is Bulgarian),
with an English gloss in this design doc only, for review.

## 1. Why this is needed (the problem)

Today's scorecard is a technical dump: criterion IDs (`identify_a1`, `no_start_with_offer2`), primitive
names, `tier`, and raw evidence dicts (`{'before_at': 104, 'after_at': 310}`). A team leader cannot read
it. The evaluation CONTENT is right (proven on the Ана call); only its PRESENTATION is unusable.

## 2. Source-of-truth grounding (every structural choice traces here)

| Source | What it fixes about the structure |
| --- | --- |
| `ClientFiles/FirstWorkflow.md:9,13,15,17,23` | Dimensions the client watches: script elements; увереност/усмивка/емоция/дикция (L9); **започва от оферта 1 → оборва възражения → чак тогава оферта 2** (L9); required/forbidden words (**L13**); времетраене, резултат, template/break-point (L15); failure patterns — вяло, не задържат в първите секунди, лесно се предават, **не повтарят офертата, не хвалят, не дават практически ползи, не искат решение** (L17); priority order script→intonation→active-listening (L23). |
| `ClientFiles/CallScript.docx` | Mandatory script phases & order (opening → consent-to-record → offer 1 → price → device bonus → MBB/Netbox cross-sell check → legal block → 14-day withdrawal → mandatory summary → thank-you), objection branches, три-оферта escalation. Gives each item its plain-language NAME and natural GROUPING. |
| `docs/research/callcenter-harness-requirements-foundation.md:15,88,200-203` | Report is FOR team leaders (L15); FR-4.6 = **break-point / "where they break"** (L200-201); FR-4.7 = per-dimension results, mandatory-element coverage, findings-with-quotes, outcome, duration (L202-203). |
| `docs/m3-calibration-spec.md:16-17,22-31,67,119,147-154` | **No overall pass/fail score** (L16-17). Two tiers: **HARD=нарушение** (задължително/забранено), **SOFT=препоръчително** (L22-31). **deal ∈ {yes,no}** first-class (L67). **Persistence ⟂ tone** (L119). Avoid-words precedence: mandated text is never penalized (**§6**, L147-154). |

**Note on FR-4.7 "scores per dimension":** FR-4.7 predates the m3 no-score reframe (m3 §0). This design
follows m3: **no numeric per-dimension score**; instead each dimension shows met/not-met rows + a plain
verdict. The "scores" obligation of FR-4.7 is deliberately superseded by m3 §0.

## 3. Design principles (derived, not invented)

1. **Lead with the human question, not the criterion id.** Every row is a plain Bulgarian statement of
   the mandatory element (from CallScript.docx).
2. **Group by call phase / dimension, not by primitive** — reviewer reads the call top-to-bottom in the
   FirstWorkflow priority order.
3. **No fabricated overall grade** (m3 §0). Instead a factual at-a-glance banner (counts + outcome +
   duration). See §4.A for the exact counting rule.
4. **Labels state the mandatory element's INTENT; statuses come from AUTOMATED proxy checks.** This is the
   honesty rule the gates forced (satisfaction B1-B4). A ✅ means "the automated keyword/heuristic check
   passed," NOT a guarantee the agent did it perfectly; some checks are keyword proxies that can mis-fire.
   The scorecard therefore always shows the evidence quote, and every item is reviewer-overridable. Labels
   must not assert more than the check can establish (see §5 for the honesty-corrected labels).
5. **Status vocabulary — human words with HONEST meaning** (satisfaction B3-B4):
   - ✅ **Изпълнено** — the automated check passed.
   - ❌ **Пропуснато / Нарушение** — HARD check failed (a real нарушение). SOFT fail renders instead as
     ⚠️ **Препоръка** (advisory), never a red violation.
   - 🔍 **За преглед** — the automated check **could not decide** and a human should listen. Causes are
     broader than STT: STT-uncertain near-match, the AI judge returned no score, path unresolved, price
     masked by redaction, etc. Wording to the team lead: «автоматичната проверка не е сигурна — чуйте записа».
   - ➖ **Неприложимо** — the item does not apply to THIS call. Causes: no deal (a conditional item like
     the legal block), the offer-escalation never happened (order check), or the item is not required on
     this call path. (Distinct icon from 🔍 so a legend/filter can separate them.)
6. **Every judgement shows its evidence** — the exact words (FR-4.7). Technical coordinates dropped.
7. **End with the coaching takeaway** — the break-point in 1-3 sentences (FR-4.6).

## 4. Proposed scorecard structure (sections, in reading order)

### A. Заглавна част / At-a-glance (header banner)
- **Разговор** (id) · **Дата** · **Времетраене** (mm:ss) — pulled from `ctx["ingest"].duration_seconds`
  (NOT the evaluation dict — satisfaction M1).
- **Тип разговор (call path):** титуляр / друго лице «да» / друго лице «не» — the three values
  `path_select` actually emits (satisfaction M2). *(Callback re-intro is a future path — not emitted today;
  see §6b scope-out.)*
- **Състояние на разговора (whole-call disposition)** — one of: **Оценен** (fully evaluated) ·
  **Задържан за преглед** (held — low STT/redaction confidence; score is NOT authoritative, NFR-4) ·
  **Пропуснато обаждане** (skipped non-conversation: no-answer/voicemail/too-short). Held/skipped calls
  show this banner + reason and STOP — no checklist is rendered (coverage B4; FR-1.2, FR-2.3).
- **РЕЗУЛТАТ:** 🟢 **СДЕЛКА** / ⚪ **Няма сделка**, with a one-line reason and its confidence caveat when
  the signal is heuristic (e.g. «вероятна сделка — клиентът насочи куриера: 'на работа' (сигнал по
  ключова фраза)» — satisfaction M5).
- **Обобщение (counting rule, fixed):** «Задължителни: **M/H изпълнени** · **V нарушения** · 🔍 R за
  преглед · Препоръки: A». Where **H** = applicable HARD items (na excluded); **M** = HARD met; **V** =
  HARD not-met; **R** = HARD за преглед; and M + V + R = H. **A** = SOFT items not-met (advisories).
  A HARD item in 🔍 за преглед is counted in R, NOT in M (this is the bug the gates caught). **A** counts
  every SOFT row DISPLAYED as ⚠️ — advisory not-met OR mixed-signal (e.g. the tone row when the judge is
  positive but prosody flags monotone), so the banner's "Препоръки: A" always equals the number of ⚠️
  icons a reviewer sees in the SOFT sections.

### B. Спазване на скрипта / Script adherence (mandatory checklist)
Grouped by call phase, in script order. Each row: status icon · plain-BG label · evidence quote. Only HARD
items can show ❌ Нарушение. Sub-groups (every mapped criterion has a slot here):
- **Начало и съгласие** — представяне от името на А1; съгласие за запис; правилен ред (запис ПРЕДИ
  офертата); име, споменато в началото.
- **Оферта 1** — спазен ред на офертите (не започва с Оферта 2); отстъпка от месечната такса;
  скорост/канали; бонус устройство (препоръка).
- **Цена** — обявени крайни цени (поне две суми).
- **Законова част (при сделка)** — право на отказ (14 дни); законов текст при сделка; **данни за куриер
  (адрес/телефон)** (препоръка) ← this row was missing from the enumeration (readiness M6).
- **Приключване** — задължително обобщение («за Ваше спокойствие…»); учтиво приключване/благодарност.

### C. Интонация и емоция / Tone & emotion (dimension 2)
Plain verdict from TWO independent signals that must be reconciled (satisfaction M6): the AI-judge
`emotion` verdict AND the prosody `flags`. Rule: if prosody flags e.g. `monotone_delivery`, the row shows
⚠️ even when the judge says positive, and names the flag («звучи по-скоро монотонно»). Rows: увереност и
емоция (не вял); ясна дикция/темпо; задържане в първите секунди (opening density).

### D. Активно слушане и оборване на възражения / Active listening & objections (dimension 3)
SEPARATE from tone (m3 §4 "tone ⟂ persistence"): активно слушане; оборване на възражения / не се предаде.

### E. Език / Language (advisory)
Предпочитани изрази; забранени думи (освен вътре в задължителен текст — m3 §6 precedence).

### F. Какво се обърка / Coaching takeaway
1-3 sentences naming the break-point and the highest-value fix (FR-4.6), from the HARD нарушения + the
persistence/tone verdicts.

## 5. Full mapping: criterion → HONEST human label → section

Labels corrected so none overclaims its check (satisfaction B1-B4, M3-M4). "Proxy note" flags checks whose
✅ is a keyword/heuristic proxy a reviewer may want to spot-check.

| criterion id | Honest human label (BG) | Section | Tier | Proxy note |
| --- | --- | --- | --- | --- |
| `identify_a1` | Представи се от името на А1 | B·Начало | HARD | keyword match; can false-pass on an incidental «Моят А1» app mention (a1.json:192) |
| `record_consent` | Уведоми, че разговорът се записва | B·Начало | HARD | keyword |
| `consent_before_offer` | Съгласие за запис ПРЕДИ офертата | B·Начало | HARD | phrase order |
| `name_said` | Име, споменато в първите 20 сек | B·Начало | HARD | proves a person-name was spoken on the agent channel; does NOT distinguish agent's own name from addressing the client (was «обърна се към клиента по име» — overclaim) |
| `no_start_with_offer2` | Спазен ред на офертите (не започва с Оферта 2) | B·Оферта 1 | HARD | ➖ when no Offer-2 escalation happened; only flags Offer-2-before-Offer-1 (was «Започна от Оферта 1» — overclaim) |
| `discount_offer` | Предложи отстъпка от месечната такса | B·Оферта 1 | HARD | keyword |
| `speed_channels` | Представи скорост и канали | B·Оферта 1 | HARD | keyword |
| `device_bonus` | Спомена бонус устройство (слушалки/гривна) | B·Оферта 1 | SOFT | keyword |
| `price_structure` | Обяви крайни цени (поне две суми) | B·Цена | HARD | checks ≥2 currency amounts; does NOT verify the 12+12-month framing (was «(12+12 месеца)» — overclaim) |
| `right_of_withdrawal` | Прочете правото на отказ (14 дни) | B·Законова | HARD | keyword |
| `legal_read_on_deal` | Прочете законовата част при сделка | B·Законова | HARD (cond. deal) | keyword only — cannot confirm VERBATIM reading (spot-check by ear); ➖ when no deal |
| `courier_capture` | Взе данни за куриер (адрес/телефон) при сделка | B·Законова | SOFT (cond. deal) | ➖ when no deal / anchor absent |
| `final_summary` | Направи задължителното обобщение | B·Приключване | HARD | keyword |
| `polite_close` | Учтиво приключване и благодарност | B·Приключване | HARD | keyword |
| `emotion` | Уверен и емоционален тон (не вял) | C·Интонация | SOFT | AI-judge score; reconcile with prosody flags |
| *(prosody, derived — not a rubric id)* | Ясна дикция и темпо; монотонност | C·Интонация | SOFT | from prosody, no criterion id |
| `opening_density` | Задържа клиента в първите секунди | C·Интонация | SOFT | word-count heuristic on opening |
| `active_listening` | Активно слушане | D·Слушане | SOFT | AI-judge score |
| `objection_effort` | Оборване на възражения / не се предаде | D·Слушане | SOFT | AI-judge, tied to a real customer objection quote (faithful) |
| `prefer_words` | Използва предпочитани изрази | E·Език | SOFT | keyword |
| `avoid_words` | Избягва забранени думи | E·Език | SOFT | keyword; mandated-text spans excluded |
| `deal` | РЕЗУЛТАТ: сделка / няма сделка | A·Header | outcome | logistics/number heuristic — show confidence caveat |
| `path` | Тип разговор | A·Header | classification | — |

All 22 rubric ids have a home; the one non-id row (prosody diction) is explicitly marked derived.

## 6. Rendered example — the Ана call, corrected to the REAL results & honest labels

```
────────────────────────────────────────────────────────
  РАЗГОВОР: Ана Любенова · Времетраене: 10:38 · Тип: Титуляр · Състояние: Оценен
  РЕЗУЛТАТ: 🟢 СДЕЛКА  (вероятна — клиентът насочи куриера: «на работа»; сигнал по ключова фраза)
  Обобщение: Задължителни 10/11 изпълнени · 0 нарушения · 🔍 1 за преглед · Препоръки: 4
────────────────────────────────────────────────────────
  СПАЗВАНЕ НА СКРИПТА
   Начало и съгласие
     ✅ Представи се от името на А1        «…приложение Моят А1…»  (⚠ по ключова дума)
     ✅ Уведоми, че разговорът се записва   «разговорът ни се записва»
     ✅ Правилен ред (запис преди офертата)
     ✅ Име, споменато в първите 20 сек
   Оферта 1
     ➖ Ред на офертите — неприложимо (няма преход към Оферта 2 в този разговор)
     ✅ Отстъпка от месечната такса         «отстъпка от месечната такса…»
     ✅ Скорост и канали                    «…300 Мбит… над 200 канала»
     ✅ Бонус устройство (препоръка)         «Bluetooth слушалки Huawei FreeBuds»
   Цена
     ✅ Обяви крайни цени                    «21 евро… 23 евро…»
   Законова част
     ✅ Право на отказ (14 дни)             «…14 дни от датата на подписа»
     🔍 Законов текст при сделка — ЗА ПРЕГЛЕД (проверката не е сигурна; чуйте записа)
     ✅ Данни за куриер (препоръка)
   Приключване
     ✅ Задължително обобщение             «за ваше спокойствие обобщавам…»
     ✅ Учтиво приключване и благодарност
  ИНТОНАЦИЯ И ЕМОЦИЯ
     ⚠️ Тон — смесен сигнал: съдията оценява като уверен, но просодията отчита «монотонно»
     ✅ Задържа клиента в първите секунди
  АКТИВНО СЛУШАНЕ И ВЪЗРАЖЕНИЯ
     ⚠️ Оборване на възражения — слабо
     ⚠️ Активно слушане — ниско
  ЕЗИК
     ✅ Използва предпочитани изрази
     ⚠️ Забранени думи — 3 (препоръка)
  КАКВО СЕ ОБЪРКА
     Вероятна сделка, скриптът е спазен (0 нарушения). Основната зона за подобрение
     е активното слушане и оборването на възражения — агентът говори по скрипта, но
     не реагира достатъчно на клиента, а тонът клони към монотонен. Един елемент
     («законов текст») да се провери на запис заради несигурна автоматична проверка.
────────────────────────────────────────────────────────
```

## 6b. Coverage scope-outs (explicit, per coverage-gate B1-B4 / M1-M7)

These are **watched by the client but NOT in the current rubric** — surfaced here as an explicit future
list so they are not silently dropped. They require NEW rubric criteria (a separate effort), not just a
presentation change:
- **не повтарят офертата** (offer-repeat count) — evaluator already computes a repeat signal; needs a
  scored row. *(FirstWorkflow L17; FR-4.6.)*
- **не искат решение** (proactive decision-ask) — `ask_for_decision_phrases` exist in a1.json but no
  criterion consumes them.
- **не хвалят / не дават практически ползи** (praise / practical-benefit framing) — no criterion today.
- **Оферта 2 / Оферта 3 escalation** state machine (present after rebuttal; ≤2 rebuttals; never close with
  «дочуване» on refusal) — m3 §4/§8; no rubric criteria today.
- **Non-titular gating question** «Вие ли вземате решение?» (HARD on P-NONTIT, m3 §1) and other
  path-specific mandatory items — path applicability is representable (➖) but the path-specific HARD rows
  are not yet in the rubric.

**Out of first-slice scope** (stated so a reviewer isn't surprised): post-call data-entry accuracy
(order/address/comment/result — FirstWorkflow L19, foundation W4); aggregate "success-template" detection
across many calls (FR-X.2 — a cross-call view, not a single-call scorecard); усмивка as a distinct signal
(folded into tone).

## 7. Design decisions (LOCKED by Kamen — feed the next playbook)

- **D1 — Output format: (c) structured JSON "report model" + a thin renderer.** DECIDED. The evaluator (or
  a post-eval assembler) emits a stable report-model JSON; a renderer produces the human view. Keeps the
  engine hollow and lets a future UI/dashboard reuse the JSON.
- **D2 — Keep the technical checklist too: yes, behind a `--verbose` flag** (recommended default; Kamen may
  revisit) — human view by default, raw criterion rows for calibration/debug.
- **D3 — Proxy-check transparency: mark «по ключова дума» only on known false-pass-risk items** (recommended
  default; Kamen may revisit) — not on every keyword row, to avoid clutter.
- **D4 — Scope: RENDERER + NEW RUBRIC CRITERIA.** DECIDED. The next playbook covers BOTH the report-model+
  renderer AND new scoring criteria for the client-watched behaviors §6b lists as currently un-ruled. So
  §6b's "watched but not in the current rubric" list is now an **IN-SCOPE work list**, not a scope-out —
  see §6b (each will need its own grounding + calibration, like the existing criteria).

## 8. Scope note

This document defines STRUCTURE + honest labels + scope boundaries. It does NOT change scoring logic,
detection, or the rubric — those are correct as far as they go (the gates confirmed the data backbone is
real and every criterion is faithfully mappable once labels are honesty-corrected). Building a report-model
+ renderer is the next playbook, per Kamen.
