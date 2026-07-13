"""Deterministic (DET / DET-MAP) rubric check primitives (Slice 2).

Each primitive is a pure function `fn(cfg, ctx) -> {"status", "evidence"}` where:
  cfg  = the rubric entry (dict; primitive-specific params),
  ctx  = {source_text, agent_words, redaction_map, mandated_regions, duration, lang, channel},
  status ∈ {"met", "not_met", "indeterminate", "na"}.
The engine ships the primitives; the client's profile declares which run with which params — so a new
client/rubric plugs in with zero code change. CMD/AI-judge primitives are Slice 3; an unknown primitive
here returns `indeterminate(reason="deferred")` (the DET checks still score). Bodies reuse the shipped
pure checks in `evaluator.py` where they map cleanly; the rest is new per docs/slice2-plan.md D2.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from cc_harness.phase_ledger.evaluator import (
    _find_quote, _first_offset, check_forbidden, first_seconds_engagement,
)

Ctx = dict[str, Any]
Result = dict[str, Any]


def _r(status: str, **evidence: Any) -> Result:
    return {"status": status, "evidence": evidence}


# ---- DET primitives -------------------------------------------------------------------------------

def phrase_present(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """met iff any configured phrase appears in the agent transcript (case-insensitive substring)."""
    phrases = [str(p) for p in cfg.get("phrases", [])]
    quote = _find_quote(ctx["source_text"], phrases)
    return _r("met", quote=quote) if quote is not None else _r("not_met", phrases=phrases)


def phrase_ordering(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """met iff the `before` phrase-group precedes the `after` phrase-group. na if either group is absent.
    Pairwise, built on _first_offset (NOT the category-keyed check_ordering)."""
    low = ctx["source_text"].lower()
    bo = _first_offset(low, [str(p) for p in cfg.get("before_phrases", [])])
    ao = _first_offset(low, [str(p) for p in cfg.get("after_phrases", [])])
    if bo < 0 or ao < 0:
        return _r("na", before_at=bo, after_at=ao)
    return _r("met", before_at=bo, after_at=ao) if bo <= ao else _r("not_met", before_at=bo, after_at=ao)


def _mandated_char_ranges(ctx: Ctx) -> list[tuple[int, int]]:
    """Char ranges of the mandated (legal/scripted) phrases in source_text — avoid-word hits inside
    these are NOT penalized (M3 §6 precedence, plan D4)."""
    low = ctx["source_text"].lower()
    ranges: list[tuple[int, int]] = []
    for phrase in ctx.get("mandated_regions") or []:
        p = str(phrase).lower()
        idx = 0
        while p and (pos := low.find(p, idx)) != -1:
            ranges.append((pos, pos + len(p)))
            idx = pos + len(p)
    return ranges


def _count_outside_mandated(text: str, words: list[str], mandated: list[tuple[int, int]]) -> int:
    low = text.lower()
    n = 0
    for w in words:
        wl = w.lower()
        if not wl:
            continue
        idx = 0
        while (pos := low.find(wl, idx)) != -1:
            if not any(a <= pos < b for a, b in mandated):
                n += 1
            idx = pos + len(wl)
    return n


def word_prefer(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """SOFT positive signal: count preferred-word usages. met if used at least once (advisory)."""
    words = [str(w) for w in cfg.get("words", [])]
    count = _count_outside_mandated(ctx["source_text"], words, [])
    return _r("met" if count > 0 else "not_met", count=count)


def word_avoid(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """SOFT negative signal: count avoid-word usages OUTSIDE mandated spans (D4). met (good) if none."""
    words = [str(w) for w in cfg.get("words", [])]
    mandated = _mandated_char_ranges(ctx) if cfg.get("except_in_mandated_spans") else []
    count = _count_outside_mandated(ctx["source_text"], words, mandated)
    return _r("met" if count == 0 else "not_met", count=count)


def forbidden_phrase(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """HARD: configured phrases must NOT appear (surfaces check_forbidden as a rubric primitive)."""
    hits = check_forbidden(ctx["source_text"], [str(p) for p in cfg.get("phrases", [])])["forbidden_hits"]
    return _r("not_met", hits=hits) if hits else _r("met")


def opening_density(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """DET: >= min_words agent words in the first n seconds (surfaces first_seconds_engagement)."""
    res = first_seconds_engagement(ctx.get("agent_words"), float(cfg.get("n", 10)), int(cfg.get("min_words", 12)))
    if res["first_seconds_na"]:
        return _r("na")
    return _r("not_met" if res["first_seconds_flag"] else "met", words=res["first_seconds_words"])


def numeric_structure(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """met iff >= `min_values` distinct money amounts are stated (e.g. standard AND discounted price).
    `currency` markers come from the rubric entry (locale DATA — the engine holds no currency words).
    If the price segment was NUMBER-category masked, the evidence is gone → indeterminate (never a false
    not_met), per M3 §14 R-d."""
    currency = [str(c) for c in cfg.get("currency", [])]  # locale DATA from the rubric; engine holds none
    if not currency:
        return _r("indeterminate", reason="no currency markers configured")
    pat = re.compile(r"\d+[.,]?\d*\s*(?:" + "|".join(re.escape(c) for c in currency) + r")", re.IGNORECASE)
    amounts = [m.group().strip() for m in pat.finditer(ctx["source_text"])]
    need = int(cfg.get("min_values", 2))
    if len({re.sub(r"\D", "", a) for a in amounts}) >= need:
        return _r("met", amounts=amounts[:6])
    # Was a number-category span masked ON THE AGENT CHANNEL (where the price is spoken)? Then the price
    # may have been said but scrubbed → indeterminate, not a false not_met (M3 §14 R-d). A customer-channel
    # mask (e.g. their phone) must NOT defang this agent-side check.
    number_cats = {"NUMERIC_RUN", "PHONE_OR_ID", "EGN", "CARD", "IBAN", "MULTI"}
    chan = ctx.get("channel")
    if any(str(s.get("category")) in number_cats and (not chan or s.get("channel") == chan)
           for s in (ctx.get("redaction_map") or [])):
        return _r("indeterminate", reason="price segment may be number-masked (agent channel)", amounts=amounts)
    return _r("not_met", amounts=amounts)


def composite(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """ALL configured sub-element primitives must be met. any not_met → not_met; any indeterminate →
    indeterminate; else met. (e.g. device = model + lease&cash price + characteristic)."""
    statuses = []
    for el in cfg.get("elements", []):
        fn = PRIMITIVES.get(str(el.get("primitive")))
        statuses.append(fn(el, ctx)["status"] if fn else "indeterminate")
    if "not_met" in statuses:
        return _r("not_met", elements=statuses)
    if "indeterminate" in statuses or not statuses:
        return _r("indeterminate", elements=statuses)
    return _r("met", elements=statuses)


# ---- DET-MAP primitive (needs the redaction map) --------------------------------------------------

def _resolve_channel(chan: Any, ctx: Ctx) -> Any:
    """Symbolic channel resolution (hollow): a profile must not hardcode a per-recording channel id
    (left/right) — it names the ROLE and the runtime resolves it. `customer`/`agent` → the classified
    channel from ctx; anything else is a literal (or None → the default agent channel via ctx)."""
    if chan == "customer":
        return ctx.get("customer_channel")
    if chan == "agent":
        return ctx.get("channel")
    return chan or ctx.get("channel")


def _phrase_start_time(words: list[dict[str, Any]], phrases: list[str]) -> float | None:
    """Earliest start time (seconds) at which any of `phrases` begins in a word-timestamp list, or None
    if none occur. Used to anchor a dynamic region to a spoken phrase (e.g. the address-request line)."""
    if not words:
        return None
    joined, char_time = "", []  # char_time[i] = start time of the word char i belongs to (spaces incl.)
    for w in words:
        tok = str(w.get("word", ""))
        start = float(w.get("start", 0.0))
        if joined:
            joined += " "
            char_time.append(start)
        joined += tok.lower()
        char_time.extend([start] * len(tok))
    best: float | None = None
    for ph in phrases:
        idx = joined.find(str(ph).lower())
        if idx >= 0 and idx < len(char_time):
            t = char_time[idx]
            best = t if best is None else min(best, t)
    return best


def slot_present(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """DET-MAP proxy: a masked PII slot of a configured category occurred in a time region on a channel
    (proves e.g. a name was SPOKEN, without the value). Slice-2 use: crit-1 name-slot in the intro region
    on the agent channel. Slice-3 use: G6 courier-capture — a PHONE_OR_ID/address slot on the CUSTOMER
    channel AFTER the address-request phrase (region.after_phrase). `indeterminate` if the redaction map
    is absent, or a symbolic channel role is requested but that channel does not exist (mono)."""
    rmap = ctx.get("redaction_map")
    if rmap is None:
        return _r("indeterminate", reason="no redaction map")
    cats = set(cfg.get("slot_categories", []))
    chan_spec = cfg.get("channel")
    channel = _resolve_channel(chan_spec, ctx)
    if chan_spec in ("customer", "agent") and not channel:
        return _r("indeterminate", reason=f"no {chan_spec} channel")
    region = cfg.get("region") or {}
    lo, hi = float(region.get("from", 0.0)), float(region.get("to", region.get("intro_seconds", 1e9)))
    # Dynamic region anchoring: resolve `lo` to the anchor phrase's start in the anchor channel's words
    # (default the agent's — the agent speaks the address-request line). A missing anchor means the
    # precondition event never occurred, so a slot cannot be "after" it: on_missing_anchor decides whether
    # that is not-applicable (e.g. e-sign path never says the courier line → na) or a miss (not_met).
    after = region.get("after_phrase")
    if after:
        anchor_words = ctx.get(str(region.get("after_phrase_words", "agent_words"))) or []
        t = _phrase_start_time(anchor_words, list(after))
        if t is None:
            disp = str(region.get("on_missing_anchor", "not_met"))
            return _r(disp if disp in ("na", "not_met", "indeterminate") else "not_met",
                      reason="anchor phrase absent", after_phrase=list(after))
        lo = max(lo, t)
    for s in rmap:
        if channel and s.get("channel") != channel:
            continue
        if str(s.get("category")) not in cats:
            continue
        if float(s.get("start", 0.0)) < hi and float(s.get("end", 0.0)) > lo:
            return _r("met", category=s.get("category"), at=[s.get("start"), s.get("end")])
    return _r("not_met", looked_for=sorted(cats))


# ---- CMD / AI-judge primitives (Slice 3) ----------------------------------------------------------
# These read `ctx["judge"]` (the command-mode judge verdict) + the customer channel. In DETERMINISTIC
# mode ctx has no "judge" key → they return `indeterminate` (unchanged Slice-2 behavior). All use
# ctx.get(...) — never subscript — so an absent key can't KeyError.

def deal_detect(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """Resolve the call outcome from the judge verdict: deal / no_deal / refusal (+ consent). The rubric
    interpreter runs this FIRST and copies the outcome onto ctx for `conditional_on` to read."""
    judge = ctx.get("judge")
    if not judge:
        return _r("indeterminate", reason="no judge (command mode required)")
    d = judge.get("deal") or {}
    if d.get("happened"):
        outcome = "deal"
    elif d.get("refusal"):
        outcome = "refusal"
    else:
        outcome = "no_deal"
    status = "met" if outcome == "deal" else ("not_met" if outcome in ("no_deal", "refusal") else "indeterminate")
    return _r(status, deal=outcome, consent=bool(d.get("consent")))


def path_select(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """Resolve the call path from the judge verdict: titular vs non_titular (decision-maker gating) +
    the mobile/fixed service branch. The interpreter copies `path` onto ctx for applies_to_paths filtering."""
    judge = ctx.get("judge")
    if not judge:
        return _r("indeterminate", reason="no judge (command mode required)")
    p = judge.get("path") or {}
    # Fail-closed: the harness never assumes the happy path. A judge verdict that omits the gating
    # field must NOT silently resolve to titular (which would skip every non-titular applies_to_paths
    # row) — it stays indeterminate so the path-gated rows fall through to review_needed, matching the
    # mono/no-judge disposition (M3 §14 R-b).
    is_titular = p.get("is_titular")
    if is_titular is None:
        return _r("indeterminate", reason="judge omitted is_titular")
    path = "titular" if is_titular else ("non_titular_yes" if p.get("decision_maker") else "non_titular_no")
    return _r("met", path=path, service=p.get("service"))


def judge_check(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """A semantic check delegated to the command-mode judge. Reads the judge's per-id verdict; a `met`
    verdict must carry an evidence substring that actually appears in the source (NFR-5 quote-exactness,
    moved here from evaluate_command). Optional `min_score` compares a scored judge field."""
    judge = ctx.get("judge")
    if not judge:
        return _r("indeterminate", reason="no judge (command mode required)")
    verdict = (judge.get("checks") or {}).get(str(cfg.get("id"))) or {}
    if "min_score" in cfg:  # scored field (e.g. active_listening/emotion)
        score = float(verdict.get("score", 0.0))
        return _r("met" if score >= float(cfg["min_score"]) else "not_met", score=score)
    met = bool(verdict.get("met"))
    quote = str(verdict.get("evidence", "") or "")
    if met and quote and quote.lower() not in ctx.get("source_text", "").lower():
        met = False  # a met verdict with an unquotable/fabricated evidence is downgraded (fail-closed)
    return _r("met" if met else "not_met", evidence=quote, detail=verdict.get("detail"))


# ---- conditional wrapper --------------------------------------------------------------------------

def conditional_on(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """Run the wrapped check only when its condition holds. Condition state {deal, consent, refusal} is
    resolved by `deal_detect` onto ctx (Slice 3). If the condition is FALSE → `na` (not applicable). If
    the state is ABSENT (deterministic mode / no judge) → `indeterminate`. `external` (e-sign/GDPR) → EXT
    indeterminate. Unknown condition → fail-closed indeterminate."""
    cond = str(cfg.get("condition", ""))
    if cond == "external":
        return _r("indeterminate", reason="external condition (EXT, scoped out)")
    if cond in ("deal", "refusal"):
        state = ctx.get("deal")  # set by deal_detect
        if state is None:
            return _r("indeterminate", reason=f"condition '{cond}' unresolved (no judge)")
        if state != cond:
            return _r("na", reason=f"condition '{cond}' not met (deal={state})")
    elif cond == "consent":
        state = ctx.get("consent")
        if state is None:
            return _r("indeterminate", reason="condition 'consent' unresolved (no judge)")
        if not state:
            return _r("na", reason="no consent")
    elif cond:
        return _r("indeterminate", reason=f"unknown condition '{cond}' (fail-closed)")
    inner = cfg.get("check") or {}
    fn = PRIMITIVES.get(str(inner.get("primitive")))
    return fn(inner, ctx) if fn else _r("indeterminate", reason="deferred")


PRIMITIVES: dict[str, Callable[[dict[str, Any], Ctx], Result]] = {
    "phrase_present": phrase_present,
    "phrase_ordering": phrase_ordering,
    "word_prefer": word_prefer,
    "word_avoid": word_avoid,
    "forbidden_phrase": forbidden_phrase,
    "opening_density": opening_density,
    "numeric_structure": numeric_structure,
    "composite": composite,
    "slot_present": slot_present,
    "conditional_on": conditional_on,
    "deal_detect": deal_detect,      # CMD (Slice 3) — indeterminate without a judge
    "path_select": path_select,      # CMD (Slice 3)
    "judge_check": judge_check,      # CMD (Slice 3)
}
RESOLVER_PRIMITIVES = ("deal_detect", "path_select")  # run first; write deal/consent/path onto ctx


def run_primitive(name: str, cfg: dict[str, Any], ctx: Ctx) -> Result:
    """Dispatch to a primitive; an unknown/not-yet-implemented one (CMD, Slice 3) is `indeterminate`."""
    fn = PRIMITIVES.get(name)
    if fn is None:
        return _r("indeterminate", reason="deferred")  # e.g. deal_detect/path_select/judge_check (Slice 3)
    return fn(cfg, ctx)
