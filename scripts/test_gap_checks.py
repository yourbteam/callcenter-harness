#!/usr/bin/env python3
"""Unit tests for the ClientFiles gap-check pure functions (G1 ordering, G2 forbidden/phrasing,
G4 first-seconds, G5 persistence, G6 duration). Run: PYTHONPATH=src python3 scripts/test_gap_checks.py"""
import sys
from cc_harness.phase_ledger import evaluator as E

def ck(n, c):
    print(f"[{'PASS' if c else 'FAIL'}] {n}")
    if not c: sys.exit(1)

def main():
    src = "здравейте, имаме отстъпка. вече разполагате с 100 mbps и netflix. да запишем ли?"
    catkw = {"offer1_discount": ["отстъпк"], "select_packages": ["netflix"], "upsell_speed_channels": ["mbps"]}
    r = E.check_ordering(src, catkw, [{"before": "offer1_discount", "after": "select_packages"}])
    ck("G1 ordering ok", r["ordering_ok"] is True and not r["ordering_violations"])
    r = E.check_ordering("netflix ... отстъпк", catkw, [{"before": "offer1_discount", "after": "select_packages"}])
    ck("G1 ordering violation", r["ordering_ok"] is False and len(r["ordering_violations"]) == 1)
    ck("G1 ordering na", E.check_ordering("само отстъпк", catkw, [{"before": "offer1_discount", "after": "select_packages"}])["ordering_na"] is True)
    ck("G2 forbidden hit", E.check_forbidden(src, ["netflix"])["forbidden_hits"] == ["netflix"])
    ck("G2 forbidden na", E.check_forbidden(src, [])["forbidden_na"] is True)
    ck("G2 phrasings missing", E.check_required_phrasings(src, ["14 дни"])["required_phrasings_missing"] == ["14 дни"])
    words = [{"word": "a", "start": 1}, {"word": "b", "start": 2}, {"word": "c", "start": 30}]
    r = E.first_seconds_engagement(words, n=10, min_words=3)
    ck("G4 window count", r["first_seconds_words"] == 2 and r["first_seconds_flag"] is True)
    ck("G4 na no timestamps", E.first_seconds_engagement(None, 10, 12)["first_seconds_na"] is True)
    r = E.persistence("отстъпк ... отстъпк ... да запишем", ["отстъпк"], ["да запишем"])
    ck("G5 repeats+ask", r["offer_repeats"] == 1 and r["ask_for_decision_count"] == 1 and r["persistence_flag"] is False)
    ck("G5 flag no ask", E.persistence("отстъпк", ["отстъпк"], ["да запишем"])["persistence_flag"] is True)
    print("\nALL GAP-CHECK UNIT TESTS PASS")

if __name__ == "__main__":
    main()
