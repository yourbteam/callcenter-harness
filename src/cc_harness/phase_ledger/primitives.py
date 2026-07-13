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

def slot_present(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """DET-MAP proxy: a masked PII slot of a configured category occurred in a time region on a channel
    (proves e.g. a name was SPOKEN, without the value). Slice-2 use: crit-1 name-slot in the intro region
    on the agent channel. `indeterminate` if the redaction map is absent."""
    rmap = ctx.get("redaction_map")
    if rmap is None:
        return _r("indeterminate", reason="no redaction map")
    cats = set(cfg.get("slot_categories", []))
    channel = cfg.get("channel") or ctx.get("channel")
    region = cfg.get("region") or {}
    lo, hi = float(region.get("from", 0.0)), float(region.get("to", region.get("intro_seconds", 1e9)))
    for s in rmap:
        if channel and s.get("channel") != channel:
            continue
        if str(s.get("category")) not in cats:
            continue
        if float(s.get("start", 0.0)) < hi and float(s.get("end", 0.0)) > lo:
            return _r("met", category=s.get("category"), at=[s.get("start"), s.get("end")])
    return _r("not_met", looked_for=sorted(cats))


# ---- conditional wrapper --------------------------------------------------------------------------

def conditional_on(cfg: dict[str, Any], ctx: Ctx) -> Result:
    """Run the wrapped check only when its condition holds. Condition sources {deal, consent, refusal}
    come from deal_detect (Slice 3) → in Slice 2 they're unresolved → `indeterminate` (never a silent
    pass). `external` conditions (e-sign/GDPR) are EXT → indeterminate(reason=external)."""
    cond = str(cfg.get("condition", ""))
    if cond in ("deal", "consent", "refusal"):
        return _r("indeterminate", reason=f"condition '{cond}' unresolved (needs deal_detect, Slice 3)")
    if cond == "external":
        return _r("indeterminate", reason="external condition (EXT, scoped out)")
    if cond and cond not in ("deal", "consent", "refusal", "external"):
        return _r("indeterminate", reason=f"unknown condition '{cond}' (fail-closed)")  # not fail-open
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
}


def run_primitive(name: str, cfg: dict[str, Any], ctx: Ctx) -> Result:
    """Dispatch to a primitive; an unknown/not-yet-implemented one (CMD, Slice 3) is `indeterminate`."""
    fn = PRIMITIVES.get(name)
    if fn is None:
        return _r("indeterminate", reason="deferred")  # e.g. deal_detect/path_select/judge_check (Slice 3)
    return fn(cfg, ctx)
