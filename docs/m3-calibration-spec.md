# M3 Calibration Spec — client intake structured into gap-closing context

**Status:** research findings (build-bound; hardening via the three gates). **Not yet implemented.**
**Sources:** client emails 2026-07-11 (Катя/Кари) [E-DATE]; `ClientFiles/CallScript.docx` [S-Lnn];
current contract `contracts/callcenter-newplan-esign.json` [C]; earlier 5-file live sweep [SWEEP].
Every row cites its source or is marked **(inference)**.

**Script line-number scheme (pinned, reproducible):** `[S-Lnn]` = RAW paragraph index into
`CallScript.docx` — split `word/document.xml` on `</w:p>`, keep ALL paragraphs incl. blanks, number
from 1 → **195 paragraphs**. (Regenerate: unzip the docx, `re.split(r"</w:p>", xml)`, index+1.) All
`[S-Lnn]` below use this one scheme (Gate-1 fix: the earlier draft mixed a blank-stripped scheme for the
objection block with RAW for the legal block — reconciled to RAW everywhere).

---

## 0. Scoring model — the reframe (CONFIRMED by Kamen 2026-07-11)
- **No overall pass/fail score.** Each mandatory item is reported **met / not-met**; there is no
  "≥X of N = pass" threshold. [E: Катя "няма пас или не пас за целия разговор, следим дали всяко нещо
  е спазено или не"]
- **Call success = DEAL yes/no**, a SEPARATE outcome from script compliance. [E: "дали разговорът е
  успешен се определя от това дали има сделка"]
- **Two severity tiers** [E: Катя confirm]:
  - **HARD (violation / нарушение):** items phrased задължително / забранено. Binary.
  - **SOFT (advisory / closing-effectiveness):** items phrased препоръчително / избягваме. Helps or
    hurts the deal; NOT a violation.
- **Output shape:** the current `evaluate()` ledger already carries a per-category `items` list, but its
  headline is a single `manager_summary.adherence_score = matched_mandatory/total_mandatory`
  (evaluator.py:177) — that scalar is what must go. New shape: per-criterion checklist rows {criterion,
  path-applicability, tier, conditional-on, met/not-met, evidence} + a deal outcome + advisory signals;
  no aggregate pass/fail. [C evaluator.py:177,185; SWEEP]

---

## 1. Call-path taxonomy — top-level branch (NEW contract block: `call_paths`)
The harness currently has ONE implicit path. Intake defines several. Path drives which checklist applies.
- **P-TIT — titular on the line:** the deal-path sequence (§3). [E: "Задължителни стъпки … Сделка"]
- **P-NONTIT — non-titular on the line** (user/relative/colleague): steps 1–3, then the **gating
  question "Вие ли вземате решение относно тази услуга?"** →
  - **YES** → run the deal-path (§3 steps 4–13), then ask a **contact phone for the титуляр**, positive
    close; a **follow-up call** to that number; legal part per accepted offer.
  - **NO** → ask a **contact number for the титуляр** and END. [E: non-titular email]
  - **Non-titular checklist criteria (G9 — met/not-met on P-NONTIT):** (a) gating question asked (crit 4);
    (b) YES-branch: **titular contact phone collected** + positive close + deal-path steps; (c) NO-branch:
    **titular contact number collected** + end; (d) any **follow-up/callback re-opens with re-introduction
    + re-record notice** [S-L98 "При повторно обаждане… разговорът се записва"].
- **Courier data collection (G6, deal-path close, criterion 8 extension):** when delivery is courier,
  the agent must take the **address where the ТИТУЛЯР is during working hours 9–18** + a **contact mobile
  for the courier** [S-L112/L132/L148/L164/L182]. Load-bearing especially on P-NONTIT (titular absent).
  Observable as **DET-MAP** (§14 R-a): a `PHONE_OR_ID`/address mask span after the address-request phrase
  proves capture occurred; the values stay masked. The ASK itself is DET (phrase survives on stereo agent channel).
- **Service branch (within the offer step):** **mobile re-sign** vs **fixed re-sign** → DIFFERENT
  required offer parameters (§3 step 4). [E: deal-path email]
- **Offer outcome:** offer 1 / offer 2 / offer 3 (usually keep-current/reset) accepted, or refusal. [E]
- **[SWEEP reconciliation]:** the earlier call `1783081704` scored 0.125 because it is a **retention /
  keep-conditions (offer-3 / reset)** call, not the new-plan-discount path — NOT a harness bug; it is a
  different call-path/offer outcome. This taxonomy is what the sweep was missing.

---

## 2. Deal detection (E1) — gates success + the conditional checks
- **Why first:** success = deal (§0), and the legal-verbatim / detailed-summary / device-after-consent
  / new-service steps are all **conditional on consent** (§3). So deal detection is a prerequisite.
- **Signals (inference, to validate on audio):** client agreement + agent moving to **address for
  document delivery** — the decision-request phrase set "При съгласие от ваша страна, на кой адрес
  желаете да ви изпратя документите" [S-L55] and the offer-close courier variant [S-L24]; the **summary**
  "За Ваше спокойствие да обобщя – ПРИЕМАТЕ…" [S-L120/139/157/171/192]; and the **legal part** being read.
- **Output:** `deal ∈ {yes, no}` on the run; drives success + conditional-check applicability.
- **Feasibility (§14 R-b):** the customer's consent "да" is on the CUSTOMER channel, which the default
  deterministic `evaluate()` does not receive → deal detection is **command-mode (CMD)**, OR requires
  feeding `customer_text` into `evaluate()`. Agent-side signals (address-request, summary, legal reading)
  survive on the stereo agent channel and give a partial agent-side proxy; the customer confirmation does not.

---

## 3. Mandatory checklist (criteria) — maps to `categories_detail` (12 today) + additions
Legend: tier H=hard(задължително), S=soft; cond = conditional on (consent/deal). "Home" = existing
contract category (by keyword signature [C]) or **NEW**.

| # | Criterion | Path | Tier | Cond | Home (contract) |
|---|-----------|------|------|------|-----------------|
| 1 | Представяне: "от името на А1" (DET) + **a name was said** (титуляр/self) — DET-MAP proxy via a masked name-slot in the intro (§14 R-a; name CONTENT stays excluded per contract §3.5) | all | H | — | cat `А1/от името` + redaction-map name-slot |
| 2 | Уведомяване, че разговорът се записва | all | H | — | cat `записва/обслужване` |
| 3 | Уточняване за коя услуга (мобилен номер / фиксиран адрес) | all | H | — | **NEW category** |
| 4 | Gating question "Вие ли вземате решение?" | P-NONTIT | H | — | **NEW category** |
| 5 | Offer presentation w/ **branch params** (mobile vs fixed, §3a) | all | H | — | cats `отстъпк`,`Mbps/канал`,`евро/такса` (extend) |
| 6 | **Price: standard AND discounted** stated (structure, §5) | all | H | — | cat `евро/месеца/такса` (extend) |
| 7 | Device presentation: **model + lease price + cash price + short characteristic** | all | H | — | cat `слушалк/Huawei/гривн` (extend) |
| 8 | Procedure summary + **ask delivery address** (decision-request) [S-L24/L55] | all | H | cons | `ask_for_decision_phrases` [C] |
| 9 | Objection handling per state machine (§4) | all | H+S | — | `objection_cues` [C] + **NEW logic** |
| 10| After consent: ask to also send **device** (lease/cash) | all | H | cons | cat `post_acceptance_questions` (`рутер/слушалките`, S-L29) |
| 11| Offer a **new service** (дейта карта/нетбокс…) | all | H | cons | cat `MBB/Netbox/карта` |
| 12| **Legal part read VERBATIM**, correct variant (§7) | all | H | deal | cats `14 дни`,`обобщ` + **NEW variant-select logic** |
| 13| Right of withdrawal (14 дни) | all | H | deal | cat `14 дни/откажете/неустойка` |
| 14| Detailed final summary ("ПРИЕМАТЕ оферта за…") | all | H | deal | cat `обобщ/приемате` |
| 15| "Има ли още нещо, което желаете да обясня?" | all | H | deal | **NEW category** (or extend `обобщ`) |
| 16| Учтив финал (благодаря за времето) | all | H | — | cat `благодар/приятен ден` |

### 3a. Offer-presentation branch parameters (criterion 5) [E: deal-path email]
- **Mobile re-sign:** национални минути; MB на макс. скорост; MB роуминг; безплатни SMS/MMS; брой
  „услуги селект" + безплатни месеци; стандартна цена; промо цена г1 и г2.
- **Fixed re-sign:** брой канали; скорост интернет; брой „услуги селект" + безплатни месеци; стандартна
  цена; промо цена г1 и г2; брой доп. приемници + цена (ако има).
- Harness must **detect the branch** then check the matching parameter set.

---

## 4. Objection / persistence state machine (criterion 9) — distinct dimension (NEW logic E5/E7)
Flow [E: deal-path email + objection email; objection block S-L39–L106]:
1. **1st objection → MANDATORY** the "Не желая да се възползвам/доволен/оставам си така" rebuttal. [S-L40] (H)
2. **2nd objection matching the 1st** → short **Offer 2** presentation (branch params, §3a) + ask address. (H)
3. **2nd objection differing** → the matching scripted rebuttal (висока цена/скъпо [S-L77] / ще изчакам да
   изтече [S-L68] / кога ми изтича [S-L61] / ще посетя магазин [S-L74]); on refusal → Offer 2 + address. (H)
4. **Refusal of Offer 2** → use scripted objection responses. (H)
5. **Offer 3** (usually keep-current/reset) → present AFTER the post-offer-2 rebuttal, **insist** address. (H)
Rules: **≤2 rebuttals on offer 1** then move to offer 2 [E задължително] (H); **never close with
"дочуване" on a refusal** [E "задължително … да не приключва разговора с дочуване"] (**H, grounded**);
**do not self-initiate a callback** ("мога да ви звънна отново"…) [E — listed under "избягваме"] (**S,
grounded**); target deferred calls ≤ 1/3 of completed [E] (out-of-scope KPI).
**Persistence is a SEPARATE dimension from tone** [E: "тонът не е вял, но се предават лесно"].
- **Objection-subtype decomposition (G14):** not every "objection" belongs to this §4 offer state machine.
  **Crosssell refusal** [S-L106 "Имам интернет/телевизия на адреса"] belongs to criterion 11 (new-service),
  NOT §4. **Router-rent refusal** [S-L105] belongs to the keep-with-router/device dimension. **"Не желая
  да разговарям"** [S-L94] is an early-objection variant handled by step 1. **Technical-complaint redirect**
  [S-L100/L104] is a **non-sales branch** → §13 [OPEN-NONSALES]. Each is scored in its own dimension.

---

## 5. Price explanation (criterion 6) — RESOLVED [E: Кари]
Every offer has a **standard** monthly fee AND a **discounted** fee for the contract period; agent must
state **both**. Frame [S: "вместо стандартната цена …евро, специално за Вас … само …евро за първите 12
месеца и … за вторите 12 месеца"]. **Check = both a standard price and a discounted price articulated,
ideally with the г1/г2 split — verify STRUCTURE, not the live figures** (per-client dynamic).
**Redaction hazard (§14 R-d):** normal frames survive (each figure is ≤3 number-tokens between
евро/за/месеца, below the mask thresholds), but if STT renders adjacent figures as one digit run (≥5
digits) or ≥4 consecutive number-words, the whole price segment is masked → the criterion is
**INDETERMINATE → human review**, never auto-not-met.

---

## 6. Words — preferred vs avoid (NEW `preferred_words`; existing `forbidden_words` [C])
- **Prefer (S, positive):** "Ще"-forms (ще получите/ще изпратя); отстъпка; получавате; вземате; полага
  ви се. [E]
- **Avoid (S, negative):** купувате; таксуваме; такса (overuse); можете/мога/бих могъл family; "ще ви се
  вдигне таксата"; agent-initiated callback offers. [E]
- **Забранено (H):** starting the call with **Offer 2** [E "забранено"] — detected via §8.
- Tier rule [E: Катя]: забранено = categorical violation; препоръчително/избягваме = advisory.
- **PRECEDENCE (G15/G2 — critical): mandated script text overrides the soft avoid-word penalty.** The
  avoid-word scorer (E4) MUST NOT penalize avoid-words that occur INSIDE mandated spans — the verbatim
  legal part (§7) and the scripted objection rebuttals (§4) — where the script itself uses "можете"
  [S-L7/L24], "такса доставка" [S-L116] and "активационна такса" [S-L188]. Count avoid-words only in the
  agent's FREE (non-scripted) speech. So "такса" inside "такса доставка / активационна такса" in the
  mandated legal block is NOT a penalty. Without this rule the scorer would punish the agent for reading
  the required script.

---

## 7. Legal-verbatim (criterion 12) — conditional, **5 variants** (NEW logic E6)
- **Only when deal=yes.** [E: Кари — read at the end of a call with a deal]
- **5 verbatim legal variants** in the script (RAW headers), selected by **offer-type × device**:
  | Variant | Offer type | Device | Header | Withdrawal | Summary |
  |---|---|---|---|---|---|
  | V1 | new tariff plan | no device | [S-L108] | [S-L119] | [S-L120] |
  | V2 | RESET (keep-current) | no device | [S-L128] | [S-L138] | [S-L139] |
  | V3 | new tariff plan | with device | [S-L145] | [S-L156] | [S-L157] |
  | V4 | RESET (keep-current) | with device | [S-L163] | [S-L170] | [S-L171] |
  | V5 | re-sign **+ new service** | (per offer) | [S-L180] | [S-L191] | [S-L192] |
  Axes: offer-type ∈ {new-plan, reset, re-sign+new-service} × device {yes/no}; the re-sign+new-service
  case has a single variant (V5). Agent must read the one matching the accepted offer. [E]
- **Verbatim** = read word-for-word, not just keyword presence → needs a text-closeness check, not the
  current keyword `minimum_count`; the closeness threshold must be calibrated (see §13 [OPEN-VERBATIM]).
- **Delivery-path selector (G3):** V1/V2 headers are **`/с е-подпис/`** (Моят А1 link + 24h courier
  fallback window [S-L24/L110/L113]); V4/V5 headers are **`/само по куриер/`**; V3 is courier via its body
  ([S-L148] "до 4 работни дни ще ви изпратим по куриер"), not its header. Rule:
  **with-device ⇒ courier-only.** The accepted-offer's device flag therefore also selects the
  delivery-path text; E6 must check the delivery-path element matches (e-sign vs courier).
- **Conditional legal sub-elements (G1/G2/G4/G5/G13 — E6 must handle CONDITIONAL segments, not one flat
  closeness match):** a missing sub-element is a violation ONLY when its condition holds.
  - **GDPR consent-form** line [S-L135/L149/L166/L185] — condition ("ако няма чек за GDPR") is **external
    CRM data → EXT, scoped out** of audio-only scoring (§14 R-c; §13).
  - **3.07€ remote-order fee** [S-L116/L137/L153/L167/L188] — condition (client did NOT e-sign) is decided
    **off-call → EXT, scoped out** (§14 R-c; §13).
  - **Personal-signing mandate** "разписан само и единствено ЛИЧНО от Вас" [S-L149/L166/L184] — always
    present in the deal legal part; **observable (DET)**.
  - **24-month term** "за период от 24 месеца" [S-L134/L164/L171] — reset/keep variants.
  - **Minor fees:** autopay discount (0.50€ [S-L18] / 0.51€ [S-L96] — source doc varies; structure not
    figure is scored); 7.67€ new-service activation [S-L188] — when applicable; observable only if not
    number-masked (else INDETERMINATE, §14 R-d).

---

## 8. Offer detection & sequencing (probabilistic) — RESOLVED [E: Кари]
Offers are per-client dynamic; **offer-1-vs-2 is NOT 100% trackable even for the client.**
- **P1 (primary, most reliable):** the **offer-2 transition phrase** [S-L25 "ПРЕХОД КЪМ ОФЕРТА 2 …
  Предвид това което споделихте ще направя нещо специално … друг тарифен план … още една отстъпка"]. Its presence marks
  offer 2; appearing as the FIRST offer = **"started with offer 2" → HARD violation** (§6 забранено).
  **Alternate offer-2/3 markers the detector must also match (G8):** [S-L26 "Преход към оф 2 Ресет с
  рутер за 1.02 евро"] and [S-L27 "Трета оферта РЕСЕТ"] — a call opening on ANY of L25/L26/L27 with no
  prior distinct offer counts as started-with-offer-2/3.
- **P2 (weak):** only ONE offer presented → likely offer 2 (not certain). **P3 (weak):** a direct
  keep-current offer → often offer 2/3 (not certain).
- **Decision:** use P1 for the hard "don't start with offer 2" check; treat overall offer-1-first /
  sequencing as **ADVISORY / flag-for-human-review**, not an auto-violation (client says non-deterministic).

---

## 9. Tone / prosody (M2) — calibrate from exemplars
- **Positive set** (5 recs, `~/.claude/uploads/b05f640b-…/`): confident, LOUD, no pauses, drives to
  close. → anchors the POSITIVE end: energy floor, pace band, low-pause. [E]
- **Low-persistence set** (5 recs): OK tone, gives up easily. [E "тонът не е вял, но се предават лесно"]
- **KEY (inference, client-grounded):** **tone ⟂ persistence** — score independently. A call may sound
  energetic and still fail persistence (§4). Fill `prosody_thresholds` [C] from the positive set;
  persistence is a §4 script/behavior check, NOT a prosody threshold.

---

## 10. GAP → closing-context crosswalk (the deliverable's core)
| Original open item | Resolved decision | Lands in |
|---|---|---|
| Success threshold | No score; per-criterion checklist + deal outcome | §0 scoring model + E2 |
| 40–50/day KPI | Out (agent KPI) | dropped |
| Offer 1/2 content | Dynamic; transition-phrase primary; sequencing advisory | §8 + `call_paths`/logic E5 |
| Clear price | Standard + discounted structure | §5 + criterion 6 + E8 |
| Scripted rebuttals | In script S-L39–106 | §4 + `objection_cues` |
| Verbatim legal | Conditional on deal; 5 variants (offer-type × device) | §7 + E6 |
| Hard vs soft | забранено=hard, препоръчително=soft | §0 two tiers + E3 |
| Titular vs non-titular | Two call-paths + gating question | §1 `call_paths` + path-classify |
| Mobile vs fixed | Branch-specific offer params | §3a + branch check |
| Tone exemplars | Positive/negative reference sets | §9 prosody calibration |

---

## 11. Build work implied (data-fillable vs new logic) — for the follow-on plan, NOT this research
- **Contract JSON (data-fillable now):** criteria 1–16 as categories; `preferred_words` (NEW);
  `forbidden_words` (fill); `objection_cues` (fill from §4); `ask_for_decision_phrases` (fill);
  `ordering` (fill: decision-before-floor, no-start-with-offer-2); `call_paths` (NEW: P-TIT/P-NONTIT +
  gating); branch param sets (NEW); offer-2 transition phrase (NEW); 4 legal variants (NEW);
  price-structure markers (NEW). `prosody_thresholds` from §9.
- **Runtime prerequisite (§14 — do FIRST):** change the evaluator/runner signatures to pass the
  **redaction map** and the **customer channel text** into `evaluate()` (both modes). Class DET-MAP and
  CMD checks are impossible without this. This gates E1/E5/E6/E7/path-classify.
- **Evaluator logic (needs the write-code loop):** E1 deal-detection; E2 per-criterion checklist output;
  E3 two-tier severity; E4 preferred/avoid word scoring; E5 offer state machine (uses P1); E6 conditional
  legal-verbatim + variant select; E7 decision-before-floor + no-"дочуване"-on-refusal; E8 price-structure;
  path-classification (titular/non-titular + gating answer); mobile/fixed branch param check; persistence
  scoring independent of tone.

---

## 12. Validation assets & what each proves
- **10 exemplar recordings** (5 positive-tone, 5 low-persistence) — prosody thresholds (§9) + the
  tone⟂persistence independence claim.
- **Tomorrow's audio** (deal / no-deal / refusal, titular + non-titular) — E1 deal detection, path
  classification, the offer state machine (§4/§8), conditional legal (§7).

---

## 14. Runtime observability & check feasibility (Gate-3 satisfaction resolutions)
**Root cause (code-grounded):** the M3 evaluator's ONLY inputs are the two **PII-redacted** channel
transcripts + the prosody summary (runner.py:321-346). It does NOT receive the **redaction map** (which
alone records that a name/phone/address span was masked — category+timestamp only, no values,
runner.py:210-212), and in the **default `deterministic` mode** `evaluate()` receives **no customer
channel** (evaluator.py:136-138; `customer_text` reaches only `evaluate_command`, runner.py:346). Also
`call_path_classify` sets `call_path` from static config (runner.py:302) — it does NOT detect
titular/non-titular or mobile/fixed. Every check below is re-scoped to what is actually observable.

**Required runtime change (prerequisite for the build — add to §11):** pass the **redaction map** and the
**customer channel text** into the evaluator in BOTH modes. Without this, the checks in class DET-MAP and
CMD below cannot be satisfied. This is an evaluator/runner signature change, not just contract data.

**Check feasibility partition:**
| Class | Meaning | Checks |
|---|---|---|
| **DET** | agent-side, survives redaction, works in deterministic mode | words (§6, non-PII), ask-for-decision phrase present (crit 8 ASK), offer-2/3 transition markers (§8), summary/thank-you/right-of-withdrawal phrasing (crit 13/14/16), objection rebuttal phrases (§4), mobile/fixed cue word (crit 3, stereo only — §8/#8) |
| **DET-MAP** | needs the redaction MAP (proxy: "a PII slot was masked in region X") | crit 1 titular-name **said** = a `NER`/name span masked in the intro region (proves a name was uttered, NOT that it was the correct titular — **partial/proxy**, confirm acceptable); G6 phone/address **captured** = a `PHONE_OR_ID`/address span masked after the address-request phrase |
| **CMD** | needs the CUSTOMER channel and/or semantic judgment → **command-mode only** | E1 deal detection (customer "да"/consent), P-NONTIT gating YES/NO answer, path classification (titular/non-titular), objection-match semantics (§4 "2nd matches 1st"), active-listening/emotion |
| **EXT** | condition lives OUTSIDE the call — **not scorable from audio**, scope out unless external data wired | 3.07€ fee "if client does NOT e-sign" (e-sign happens later, off-call); GDPR-form "ако няма чек за GDPR" (CRM data) |

**Resolutions:**
- **R-a (DET-MAP):** feed the redaction map so crit-1/G6 become **PII-slot-presence** proxies (a name/
  phone/address WAS spoken/captured, via the mask event) — no PII value re-exposed, consistent with the
  contract's §3.5 name/address exclusion. Proxy caveat: confirms a name was said, not its correctness.
- **R-b (CMD):** E1 deal detection, gating YES/NO, path classification, and objection-match are
  **command-mode-only** (or require feeding `customer_text` into deterministic `evaluate()`). The spec's
  "success = deal" gate and the P-NONTIT branch therefore do NOT function in the default deterministic
  mode as-is. Decision needed: run M3 in command mode, or extend `evaluate()` to take `customer_text`.
- **R-c (EXT):** the 3.07€ fee and GDPR-form legal sub-elements are **externally conditioned** and moved
  to §13 scope-outs; personal-signing [S-L149/166/184] and 24-month term [S-L134/164/171] ARE observable
  (agent-side verbatim) and stay in §7.
- **R-d (mask-aware E6/E8):** E6 legal-verbatim closeness must **exclude masked spans** from the measure
  (align only on non-masked text, using the map) — else masked name/address slots read as false
  deviations. E8 price-structure: if the price segment is **number-category masked** (NUMERIC_RUN /
  PHONE_OR_ID whole-segment mask, redact.py:214-217), the criterion is **INDETERMINATE → route to human
  review**, NOT auto-not-met (avoids false violations). Normal price frames survive (figures are ≤3
  number-tokens between евро/за/месеца, below the mask thresholds).
- **#10 PASS:** tone⟂persistence independence HOLDS — prosody flags come from acoustics
  (evaluator.py:342-390); persistence from agent-transcript offer-repeat + ask-phrase counts
  (evaluator.py:105-116). Distinct sources; no change needed.

## 13. Still open (needs client or audio) — explicit scope-outs
- **[OPEN-AUDIO]** validate E1–E8 + path/branch detection against real deal/no-deal/refusal + non-titular
  recordings (arriving next drop).
- **[OPEN-RECONCILE]** the non-titular YES-branch step ordering was captured verbatim (steps→titular
  phone→close→follow-up→legal) and needs reconciliation with the titular ordering. (inference)
- **[RESOLVED-TIER]** "no дочуване on refusal" = **HARD** (client wording "задължително … да не приключва
  … с дочуване"); "no self-initiated callback" = **SOFT** (client listed it under "избягваме"). Both
  grounded — no longer open.
- **[OPEN-VERBATIM]** the legal-verbatim closeness threshold (how close to the scripted variant counts as
  "read дословно") must be calibrated on real deal recordings; the check replaces keyword `minimum_count`
  with a text-similarity measure (E6). Threshold value unset until audio.
- **[OPEN-KPI]** 40–50/day and deferred-calls ≤1/3 are agent-level KPIs, explicitly **out of per-call
  scope**.
- **[OPEN-CONTENT] (G7 — refer to client):** the script mandates content packages the client's intake
  step-4 parameter list OMITS — **MAX Sport plus** (stated unconditionally, [S-L12]) and **Xplore TV GO
  MAX** (3м free then 1.02€, [S-L117/L151/L189]). Script-vs-intake tension: confirm whether presenting
  these is a mandatory checklist item or optional.
- **[OPEN-NOOBJECTION] (G10 — refer to client):** how does the persistence dimension (§4) score a call
  where the client accepts offer 1 with **zero objections**? N/A (not applicable) vs auto-met. Undefined.
- **[SCOPED-OUT-EXT] (§14 R-c):** the 3.07€ remote-order fee and the GDPR consent-form line are gated on
  data that lives OUTSIDE the call (whether the client e-signs later; whether a GDPR check is on file in
  CRM). **Not scorable from audio alone** → excluded from per-call scoring unless external data is wired
  into the harness. Confirm with client that omitting these from the QA score is acceptable.
- **[DECISION-MODE] (§14 R-b — needs Kamen/client decision):** deal detection, the P-NONTIT gating
  YES/NO branch, path classification, and objection-match semantics need the customer channel →
  **run M3 in command mode**, or extend deterministic `evaluate()` to take `customer_text`. Pick one.
- **[OPEN-NONSALES] (G11 — refer to client):** disposition for **non-sales / non-offer** interactions
  (technical complaint [S-L100/L104], wrong number, refusal-before-any-offer, "не желая да разговарям"
  [S-L94] that ends the call). Which checklist (if any) applies? Today the harness HOLDs unclassifiable
  calls (fail-closed) — confirm that is the intended disposition.
