"""Generic rubric-interpreter (Slice 2): run a client's declared `rubric[]` of typed checks and emit a
per-criterion CHECKLIST + two-tier severity — the M3 reframe (no single adherence score). The engine
knows the primitives; the profile declares which checks run — a new client plugs in with zero code change.
"""

from __future__ import annotations

from typing import Any

from cc_harness.phase_ledger.primitives import Ctx, run_primitive


def run_rubric(rubric: list[dict[str, Any]], ctx: Ctx) -> dict[str, Any]:
    """Return {checklist, violations, advisories, review_needed}. Each checklist row:
    {id, primitive, tier, applies_to_paths, status ∈ {met,not_met,indeterminate,na}, evidence}."""
    checklist: list[dict[str, Any]] = []
    for entry in rubric or []:
        primitive = str(entry.get("primitive", ""))
        res = run_primitive(primitive, entry, ctx)
        checklist.append({
            "id": str(entry.get("id", "")),
            "primitive": primitive,
            "tier": str(entry.get("tier", "hard")),
            "applies_to_paths": list(entry.get("applies_to_paths") or []),
            "status": res["status"],
            "evidence": res.get("evidence", {}),
        })
    violations = [r for r in checklist if r["tier"] == "hard" and r["status"] == "not_met"]
    advisories = [r for r in checklist if r["tier"] == "soft"]
    review_needed = [r for r in checklist if r["status"] == "indeterminate"]
    return {"checklist": checklist, "violations": violations,
            "advisories": advisories, "review_needed": review_needed}
