#!/usr/bin/env python3
"""Human-scorecard report-model + renderer: grouping, the §4.A counting rule, disposition states, outcome,
and the tone-override, driven by the REAL a1.json presentation + bg.json status_labels. Fast — no model.
Run: PYTHONPATH=src python3 scripts/test_report_model.py"""
import sys
from cc_harness.config.loader import load_profile, load_language
from cc_harness.report import build_report_model, render_text

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}"); (c or sys.exit(1))

prof = load_profile("profiles/a1.json")
lang = load_language(prof.language)
PRES, LAB = prof.scorecard_presentation, lang.status_labels
ck("a1 exposes scorecard_presentation", bool(PRES.get("criteria")) and bool(PRES.get("sections")))
ck("bg exposes status_labels", bool(LAB.get("met")) and bool(LAB.get("ui")))

def row(cid, tier, status, evidence=None, paths=None):
    return {"id": cid, "primitive": "x", "tier": tier, "applies_to_paths": paths or [],
            "status": status, "evidence": evidence or {}}

# Fixture mirroring the Ана v3 titular sale (research §6): 10 hard met, 1 hard na, 1 hard review; 4 soft ⚠️.
checklist = [
    row("identify_a1", "hard", "met", {"quote": "от името на едно"}),
    row("record_consent", "hard", "met", {"quote": "разговорът ни се записва"}),
    row("consent_before_offer", "hard", "met"),
    row("name_said", "hard", "met"),
    row("no_start_with_offer2", "hard", "na", {"reason": "no offer-2 escalation"}),
    row("discount_offer", "hard", "met", {"quote": "отстъпка от месечната такса"}),
    row("speed_channels", "hard", "met", {"quote": "300 Мбит"}),
    row("price_structure", "hard", "met", {"amounts": ["21 евро", "23 евро"]}),
    row("right_of_withdrawal", "hard", "met", {"quote": "14 дни"}),
    row("legal_read_on_deal", "hard", "indeterminate", {"reason": "near-match"}),
    row("final_summary", "hard", "met", {"quote": "за ваше спокойствие обобщавам"}),
    row("polite_close", "hard", "met"),
    row("titular_check", "hard", "na", {"reason": "path titular not in scope"}, ["non_titular_yes"]),
    row("device_bonus", "soft", "met", {"quote": "Bluetooth слушалки Huawei FreeBuds"}),
    row("praise_benefits", "soft", "met", {"quote": "по-бърз интернет"}),
    row("emotion", "soft", "met", {"score": 0.5}),               # met but prosody flag → advisory (override)
    row("opening_density", "soft", "met"),
    row("active_listening", "soft", "not_met", {"score": 0.0}),  # advisory
    row("objection_effort", "soft", "not_met", {"customer_evidence": "не искам"}),  # advisory
    row("ask_for_decision", "soft", "met", {"quote": "нека го направим"}),
    row("prefer_words", "soft", "met"),
    row("avoid_words", "soft", "not_met", {"count": 3}),         # advisory
    {"id": "deal", "tier": "soft", "status": "met",
     "evidence": {"deal": "deal", "logistics": {"phrase": "на работа"}, "accept_quote": ""}},
    {"id": "path", "tier": "soft", "status": "met", "evidence": {"path": "titular"}},
]
ctx = {"evaluation": {"checklist": checklist, "violations": [], "advisories": [], "review_needed": [],
                      "intonation": {"flags": ["monotone_delivery"]}},
       "ingest": {"duration_seconds": 638.0}}

m = build_report_model(ctx, "running", PRES, LAB, call_id="Ана")
s = m["summary"]
ck("disposition = Оценен", m["header"]["disposition"] == "Оценен")
ck("duration mm:ss", m["header"]["duration_mmss"] == "10:38")
ck("outcome deal=True, heuristic", m["header"]["outcome"]["deal"] and m["header"]["outcome"]["confidence"] == "heuristic")
ck("outcome reason = на работа", m["header"]["outcome"]["reason"] == "на работа")
ck("hard_total = 11 (na excluded)", s["hard_total"] == 11)
ck("hard_met = 10", s["hard_met"] == 10)
ck("hard_violations = 0", s["hard_violations"] == 0)
ck("hard_review = 1", s["hard_review"] == 1)
ck("advisories = 4 (incl tone override)", s["advisories"] == 4)
ck("count identity met+viol+review == hard_total", s["hard_met"] + s["hard_violations"] + s["hard_review"] == s["hard_total"])
# tone override + na kind
kinds = {r["id"]: r["status_kind"] for sec in m["sections"] for r in sec["rows"]}
ck("emotion overridden to advisory (mixed signal)", kinds.get("emotion") == "advisory")
ck("no_start_with_offer2 shown as na", kinds.get("no_start_with_offer2") == "na")
ck("labels resolved (identify_a1 human label)", any(r["label"] == "Представи се от името на А1"
    for sec in m["sections"] for r in sec["rows"]))
ck("grouped into nachalo section", any(sec["id"] == "nachalo" for sec in m["sections"]))
ck("deal/path are header meta, not rows", "deal" not in kinds and "path" not in kinds)

txt = render_text(m, LAB)
ck("render contains chrome + counts", "РАЗГОВОР" in txt and "СДЕЛКА" in txt and "10/11" in txt)
ck("render contains a section title", "НАЧАЛО И СЪГЛАСИЕ" in txt)

# --- disposition: held ---
held = build_report_model({"evaluation": {"held": True, "reason": "command-mode judge: down"}}, "blocked", PRES, LAB)
ck("held → Задържан за преглед, no sections", held["header"]["disposition"] == "Задържан за преглед" and held["sections"] == [])
ck("held render omits a misleading outcome line", "Няма сделка" not in render_text(held, LAB) and "СДЕЛКА" not in render_text(held, LAB))
# --- disposition: skipped ---
skip = build_report_model({"ingest": {"skipped": True, "reason": "too short"}}, "skipped", PRES, LAB)
ck("skipped → Пропуснато обаждане, no sections", skip["header"]["disposition"] == "Пропуснато обаждане" and skip["sections"] == [])

# --- robustness: an out-of-contract hard status is surfaced as review, identity still holds ---
odd = build_report_model({"evaluation": {"checklist": [row("identify_a1", "hard", "met"),
                          row("record_consent", "hard", "weird_status")]}}, "running", PRES, LAB)
os_ = odd["summary"]
ck("unknown hard status counted in review (identity holds)",
   os_["hard_met"] + os_["hard_violations"] + os_["hard_review"] == os_["hard_total"] and os_["hard_review"] == 1)

# --- graceful fallback when presentation/labels absent ---
bare = build_report_model(ctx, "running", {}, {}, call_id="x")
ck("no-config: still builds, labels fall back to ids", bare["summary"]["hard_total"] == 11
   and any(r["label"] == "identify_a1" for sec in bare["sections"] for r in sec["rows"]))
ck("no-config render doesn't crash", isinstance(render_text(bare, {}), str))

print("\nALL REPORT-MODEL TESTS PASS")
