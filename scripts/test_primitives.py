#!/usr/bin/env python3
"""Unit tests for the Slice-2 deterministic rubric primitives. Fast (no models).
Run: PYTHONPATH=src python3 scripts/test_primitives.py"""
import sys
from cc_harness.phase_ledger.primitives import run_primitive

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

def ctx(text, **kw):
    base = {"source_text": text, "agent_words": None, "redaction_map": None,
            "mandated_regions": [], "duration": None, "channel": None}
    base.update(kw); return base

def st(name, cfg, c): return run_primitive(name, cfg, c)["status"]

# phrase_present
ck("phrase_present met", st("phrase_present", {"phrases": ["от името", "А1"]}, ctx("обажда се от името на А1")) == "met")
ck("phrase_present not_met", st("phrase_present", {"phrases": ["xyz"]}, ctx("нищо")) == "not_met")

# phrase_ordering
ck("phrase_ordering met (before precedes after)",
   st("phrase_ordering", {"before_phrases": ["записва"], "after_phrases": ["оферта"]}, ctx("разговорът се записва, ето офертата")) == "met")
ck("phrase_ordering not_met (after precedes before)",
   st("phrase_ordering", {"before_phrases": ["записва"], "after_phrases": ["оферта"]}, ctx("ето офертата, а също се записва")) == "not_met")
ck("phrase_ordering na (one absent)",
   st("phrase_ordering", {"before_phrases": ["записва"], "after_phrases": ["zzz"]}, ctx("само записва")) == "na")

# word_prefer / word_avoid + mandated-span exclusion (D4)
ck("word_prefer met", st("word_prefer", {"words": ["отстъпка"]}, ctx("голяма отстъпка днес")) == "met")
ck("word_avoid met (clean)", st("word_avoid", {"words": ["купувате"]}, ctx("нищо лошо")) == "met")
ck("word_avoid not_met (used)", st("word_avoid", {"words": ["купувате"]}, ctx("вие купувате това")) == "not_met")
ck("word_avoid EXCLUDES hits inside mandated spans (D4)",
   st("word_avoid", {"words": ["можете"], "except_in_mandated_spans": True},
      ctx("можете да откажете в 14 дни", mandated_regions=["можете да откажете в 14 дни"])) == "met")

# forbidden_phrase (HARD)
ck("forbidden_phrase not_met (present)", st("forbidden_phrase", {"phrases": ["дочуване"]}, ctx("приятен ден, дочуване")) == "not_met")
ck("forbidden_phrase met (absent)", st("forbidden_phrase", {"phrases": ["дочуване"]}, ctx("благодаря")) == "met")

# opening_density
ck("opening_density met",
   st("opening_density", {"n": 10, "min_words": 2}, ctx("x", agent_words=[{"word": "a", "start": 1.0}, {"word": "b", "start": 2.0}, {"word": "c", "start": 3.0}])) == "met")
ck("opening_density not_met (too few)",
   st("opening_density", {"n": 10, "min_words": 5}, ctx("x", agent_words=[{"word": "a", "start": 1.0}])) == "not_met")
ck("opening_density na (no words)", st("opening_density", {"n": 10, "min_words": 5}, ctx("x")) == "na")

# numeric_structure + on_masked→indeterminate (M3 §14 R-d)
ck("numeric_structure met (>=2 amounts)", st("numeric_structure", {"min_values": 2, "currency": ["евро"]}, ctx("вместо 30 евро само 19 евро")) == "met")
ck("numeric_structure not_met (1 amount)", st("numeric_structure", {"min_values": 2, "currency": ["евро"]}, ctx("само 19 евро")) == "not_met")
ck("numeric_structure INDETERMINATE when price segment number-masked",
   st("numeric_structure", {"min_values": 2, "currency": ["евро"]}, ctx("цената е", redaction_map=[{"category": "NUMERIC_RUN", "channel": "left", "start": 1.0, "end": 2.0}])) == "indeterminate")

# composite (device = all elements)
dev = {"elements": [{"primitive": "phrase_present", "phrases": ["слушалки"]}, {"primitive": "numeric_structure", "min_values": 2, "currency": ["евро"]}]}
ck("composite met (all sub met)", st("composite", dev, ctx("слушалки за 5 евро вместо 9 евро")) == "met")
ck("composite not_met (one sub fails)", st("composite", dev, ctx("слушалки без цена")) == "not_met")

# slot_present (DET-MAP)
rmap = [{"category": "GLINER_PII", "channel": "left", "start": 2.0, "end": 3.0}]
ck("slot_present met (name slot in region)",
   st("slot_present", {"slot_categories": ["NER_PER", "GLINER_PII"], "region": {"from": 0, "to": 20}}, ctx("x", redaction_map=rmap, channel="left")) == "met")
ck("slot_present not_met (slot outside region)",
   st("slot_present", {"slot_categories": ["GLINER_PII"], "region": {"from": 10, "to": 20}}, ctx("x", redaction_map=rmap, channel="left")) == "not_met")
ck("slot_present indeterminate (no map)",
   st("slot_present", {"slot_categories": ["GLINER_PII"], "region": {"from": 0, "to": 20}}, ctx("x")) == "indeterminate")

# slot_present — symbolic channel resolution (hollow: profile names the ROLE, runtime resolves it)
cmap = [{"category": "PHONE_OR_ID", "channel": "right", "start": 12.0, "end": 13.0}]
ck("slot_present symbolic customer channel → resolves + met",
   st("slot_present", {"slot_categories": ["PHONE_OR_ID"], "channel": "customer"},
      ctx("x", redaction_map=cmap, customer_channel="right")) == "met")
ck("slot_present symbolic customer channel absent (mono) → indeterminate (fail-closed)",
   st("slot_present", {"slot_categories": ["PHONE_OR_ID"], "channel": "customer"},
      ctx("x", redaction_map=cmap)) == "indeterminate")

# slot_present — phrase-anchored dynamic region (G6 courier: slot AFTER the address-request line)
words = [{"word": "на", "start": 9.0}, {"word": "кой", "start": 9.4}, {"word": "адрес", "start": 9.8}]
ck("slot_present after_phrase met (slot is after the anchor)",
   st("slot_present", {"slot_categories": ["PHONE_OR_ID"], "channel": "customer",
                       "region": {"after_phrase": ["на кой адрес"]}},
      ctx("x", redaction_map=cmap, customer_channel="right", agent_words=words)) == "met")
ck("slot_present after_phrase not_met (slot is BEFORE the anchor)",
   st("slot_present", {"slot_categories": ["PHONE_OR_ID"], "channel": "customer",
                       "region": {"after_phrase": ["на кой адрес"]}},
      ctx("x", redaction_map=[{"category": "PHONE_OR_ID", "channel": "right", "start": 2.0, "end": 3.0}],
          customer_channel="right", agent_words=words)) == "not_met")
ck("slot_present missing anchor → na (on_missing_anchor=na; e-sign path never says courier line)",
   st("slot_present", {"slot_categories": ["PHONE_OR_ID"], "channel": "customer",
                       "region": {"after_phrase": ["на кой адрес"], "on_missing_anchor": "na"}},
      ctx("x", redaction_map=cmap, customer_channel="right", agent_words=[{"word": "здравейте", "start": 1.0}])) == "na")
ck("slot_present missing anchor → not_met (default disposition)",
   st("slot_present", {"slot_categories": ["PHONE_OR_ID"], "channel": "customer",
                       "region": {"after_phrase": ["на кой адрес"]}},
      ctx("x", redaction_map=cmap, customer_channel="right", agent_words=[{"word": "здравейте", "start": 1.0}])) == "not_met")

# conditional_on: deal/consent/refusal unresolved → indeterminate (Slice 3); external → indeterminate
ck("conditional_on deal → indeterminate (Slice 3)",
   st("conditional_on", {"condition": "deal", "check": {"primitive": "phrase_present", "phrases": ["x"]}}, ctx("x")) == "indeterminate")
ck("conditional_on external → indeterminate (EXT)",
   st("conditional_on", {"condition": "external", "check": {"primitive": "phrase_present", "phrases": ["x"]}}, ctx("x")) == "indeterminate")

# a genuinely unknown primitive → indeterminate/deferred, never a crash
r = run_primitive("totally_unknown_primitive", {}, ctx("x"))
ck("unknown primitive → indeterminate deferred", r["status"] == "indeterminate" and r["evidence"].get("reason") == "deferred")

# CMD primitives WITHOUT a judge (deterministic ctx) → indeterminate (Slice-2 behavior unchanged)
ck("deal_detect no judge → indeterminate", run_primitive("deal_detect", {}, ctx("x"))["status"] == "indeterminate")
ck("path_select no judge → indeterminate", run_primitive("path_select", {}, ctx("x"))["status"] == "indeterminate")
ck("judge_check no judge → indeterminate", run_primitive("judge_check", {"id": "a"}, ctx("x"))["status"] == "indeterminate")

print("\nALL PRIMITIVE UNIT TESTS PASS")
