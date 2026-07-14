#!/usr/bin/env python3
"""Slice-3 CMD primitives + resolver-first rubric, driven by a SYNTHETIC judge verdict (no Ollama).
Run: PYTHONPATH=src python3 scripts/test_cmd_primitives.py"""
import sys
from cc_harness.phase_ledger.primitives import run_primitive
from cc_harness.phase_ledger.rubric import run_rubric
from cc_harness.phase_ledger.prompts import judge_prompt_from_rubric

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

def ctx(judge=None, text="от името на А1, приемате офертата", **kw):
    # customer_text carries the CUSTOMER's words — deal_detect now requires the acceptance quote to appear here
    base = {"source_text": text, "customer_text": "да, приемам офертата, съгласен съм",
            "agent_words": None, "redaction_map": None, "mandated_regions": [],
            "duration": None, "channel": "left"}
    if judge is not None: base["judge"] = judge
    base.update(kw); return base

# a deal now requires accept_quote (the customer's acceptance) that really appears in customer_text
DEAL = {"deal": {"happened": True, "consent": True, "refusal": False, "accept_quote": "приемам офертата"},
        "path": {"is_titular": True, "decision_maker": True, "service": "fixed"},
        "checks": {"objection_match": {"met": True, "evidence": "приемате офертата"},
                   "objection_bad": {"met": True, "evidence": "not in the transcript at all"}},
        "active_listening": {"score": 0.8}}
NODEAL = {"deal": {"happened": False, "consent": False, "refusal": True},
          "path": {"is_titular": False, "decision_maker": False}, "checks": {}}

# deal_detect
ck("deal_detect: deal→met", run_primitive("deal_detect", {}, ctx(DEAL))["status"] == "met")
ck("deal_detect: refusal→not_met", run_primitive("deal_detect", {}, ctx(NODEAL))["status"] == "not_met")
ck("deal_detect evidence carries outcome+consent",
   {k: run_primitive("deal_detect", {}, ctx(DEAL))["evidence"][k] for k in ("deal", "consent")}
   == {"deal": "deal", "consent": True})
# EVIDENCE-FORCED: happened=true but the acceptance quote is NOT in the customer transcript → no sale
ck("deal_detect: happened but accept_quote absent from customer_text → no_deal (fail-closed)",
   run_primitive("deal_detect", {}, ctx({"deal": {"happened": True, "accept_quote": "нещо което клиентът не е казал"}},
                                        customer_text="не, благодаря, не ме интересува"))["status"] == "not_met")
ck("deal_detect: happened but empty accept_quote → no_deal",
   run_primitive("deal_detect", {}, ctx({"deal": {"happened": True, "accept_quote": ""}}))["status"] == "not_met")

# path_select
ck("path_select: titular", run_primitive("path_select", {}, ctx(DEAL))["evidence"]["path"] == "titular")
ck("path_select: non_titular_no", run_primitive("path_select", {}, ctx(NODEAL))["evidence"]["path"] == "non_titular_no")
# fail-closed: judge omits is_titular → indeterminate (never silent titular)
ck("path_select: missing is_titular → indeterminate (fail-closed)",
   run_primitive("path_select", {}, ctx({"path": {"decision_maker": True}, "deal": {}, "checks": {}}))["status"] == "indeterminate")

# judge_check: met only if evidence quote is really in the source (NFR-5 quote-exactness)
ck("judge_check met (quote in source)", run_primitive("judge_check", {"id": "objection_match"}, ctx(DEAL))["status"] == "met")
ck("judge_check DOWNGRADED when evidence not in source", run_primitive("judge_check", {"id": "objection_bad"}, ctx(DEAL))["status"] == "not_met")

# require_customer_quote: an effort/rebuttal only counts if it answers a REAL customer objection (quoted + present)
REB = {"checks": {"oe": {"met": True, "evidence": "приемате офертата", "customer_evidence": "не, скъпо е"}}}
ck("require_customer_quote met (agent counter + real customer objection quote)",
   run_primitive("judge_check", {"id": "oe", "require_customer_quote": True},
                 ctx(REB, customer_text="не, скъпо е за мен"))["status"] == "met")
ck("require_customer_quote NOT met when customer_evidence absent from customer_text (rebuttal to nobody)",
   run_primitive("judge_check", {"id": "oe", "require_customer_quote": True},
                 ctx(REB, customer_text="да, чудесно, благодаря"))["status"] == "not_met")
ck("require_customer_quote NOT met when no customer_evidence at all",
   run_primitive("judge_check", {"id": "oe2", "require_customer_quote": True},
                 ctx({"checks": {"oe2": {"met": True, "evidence": "приемате офертата"}}}))["status"] == "not_met")
ck("judge_check min_score met", run_primitive("judge_check", {"id": "active_listening", "min_score": 0.5}, ctx({"checks": {"active_listening": {"score": 0.8}}}))["status"] == "met")
ck("judge_check min_score not_met", run_primitive("judge_check", {"id": "active_listening", "min_score": 0.9}, ctx({"checks": {"active_listening": {"score": 0.8}}}))["status"] == "not_met")

# conditional_on resolves against ctx set by deal_detect (via run_rubric resolver-first)
rubric = [
    {"id": "deal", "primitive": "deal_detect", "tier": "hard"},
    {"id": "legal_on_deal", "primitive": "conditional_on", "tier": "hard", "condition": "deal",
     "check": {"primitive": "phrase_present", "phrases": ["приемате"]}},
]
out = run_rubric(rubric, ctx(DEAL))
by = {r["id"]: r["status"] for r in out["checklist"]}
ck("resolver-first: deal resolved, conditional runs (met)", by == {"deal": "met", "legal_on_deal": "met"})
out2 = run_rubric(rubric, ctx(NODEAL))
by2 = {r["id"]: r["status"] for r in out2["checklist"]}
ck("conditional on deal → na when no deal", by2["legal_on_deal"] == "na")

# applies_to_paths filtering by the resolved path
rubric_p = [
    {"id": "path", "primitive": "path_select", "tier": "hard"},
    {"id": "titular_only", "primitive": "phrase_present", "tier": "hard", "phrases": ["приемате"], "applies_to_paths": ["titular"]},
    {"id": "nontit_only", "primitive": "phrase_present", "tier": "hard", "phrases": ["приемате"], "applies_to_paths": ["non_titular_yes"]},
]
outp = {r["id"]: r["status"] for r in run_rubric(rubric_p, ctx(DEAL))["checklist"]}
ck("applies_to_paths: titular check runs", outp["titular_only"] == "met")
ck("applies_to_paths: out-of-path check → na", outp["nontit_only"] == "na")
# fail-closed: path UNRESOLVED (judge omits is_titular) → path-gated rows → indeterminate, NEVER run blindly
PATHLESS = {"deal": {"happened": True, "consent": True, "refusal": False},
            "path": {"decision_maker": True}, "checks": {}}  # is_titular omitted → path_select indeterminate
outq = {r["id"]: r["status"] for r in run_rubric(rubric_p, ctx(PATHLESS))["checklist"]}
ck("path unresolved: path row indeterminate", outq["path"] == "indeterminate")
ck("path unresolved: gated row → indeterminate (fail-closed, not run-for-everyone)", outq["titular_only"] == "indeterminate")
ck("path unresolved: other gated row → indeterminate too", outq["nontit_only"] == "indeterminate")

# mono / no judge → CMD checks indeterminate (never silent no_deal)
mono = {r["id"]: r["status"] for r in run_rubric(rubric, ctx(judge=None))["checklist"]}
ck("no judge (mono): deal_detect indeterminate", mono["deal"] == "indeterminate")
ck("no judge (mono): conditional indeterminate (not na)", mono["legal_on_deal"] == "indeterminate")

# courier_capture (G6): conditional_on deal → customer-channel slot_present after the address-request phrase
CMAP = [{"category": "CONTEXT_PII", "channel": "right", "start": 40.0, "end": 42.0}]
AW = [{"word": "на", "start": 30.0}, {"word": "кой", "start": 30.4}, {"word": "адрес", "start": 30.8}]
courier = [
    {"id": "deal", "primitive": "deal_detect", "tier": "soft"},
    {"id": "courier_capture", "primitive": "conditional_on", "tier": "soft", "condition": "deal",
     "check": {"primitive": "slot_present", "channel": "customer", "slot_categories": ["CONTEXT_PII"],
               "region": {"after_phrase": ["на кой адрес"], "on_missing_anchor": "na"}}},
]
def courier_ctx(judge, **kw):
    return ctx(judge=judge, redaction_map=CMAP, customer_channel="right", agent_words=AW, **kw)
cc_deal = {r["id"]: r["status"] for r in run_rubric(courier, courier_ctx(DEAL))["checklist"]}
ck("courier_capture: deal + address-request + customer slot after → met", cc_deal["courier_capture"] == "met")
cc_nodeal = {r["id"]: r["status"] for r in run_rubric(courier, courier_ctx(NODEAL))["checklist"]}
ck("courier_capture: no deal → na", cc_nodeal["courier_capture"] == "na")
# deal but the courier line was never said (e-sign path) → na, not a false miss
DEAL_ESIGN = {**DEAL}
cc_esign = {r["id"]: r["status"] for r in run_rubric(courier, ctx(judge=DEAL_ESIGN, redaction_map=CMAP,
              customer_channel="right", agent_words=[{"word": "линк", "start": 30.0}]))["checklist"]}
ck("courier_capture: deal via e-sign (no courier line) → na", cc_esign["courier_capture"] == "na")

# judge_prompt_from_rubric: built from CMD entries (ids), no categories_detail
prompt = judge_prompt_from_rubric([{"id": "objection_match", "question": "Did the agent rebut?"}], "SRC", "PROS", "CUST")
ck("rubric judge prompt embeds the check id", "objection_match" in prompt)
ck("rubric judge prompt has no categories_detail", "categories_detail" not in prompt)
ck("rubric judge prompt asks for deal + path", '"deal"' in prompt and '"path"' in prompt)

print("\nALL CMD-PRIMITIVE (Slice 3) TESTS PASS")
