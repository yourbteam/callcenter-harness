"""Generic rubric-interpreter (Slice 2): run a client's declared `rubric[]` of typed checks and emit a
per-criterion CHECKLIST + two-tier severity — the M3 reframe (no single adherence score). The engine
knows the primitives; the profile declares which checks run — a new client plugs in with zero code change.
"""

from __future__ import annotations

from typing import Any

from cc_harness.phase_ledger.primitives import RESOLVER_PRIMITIVES, Ctx, run_primitive


def _row(entry: dict[str, Any], res: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry.get("id", "")),
        "primitive": str(entry.get("primitive", "")),
        "tier": str(entry.get("tier", "hard")),
        "applies_to_paths": list(entry.get("applies_to_paths") or []),
        "status": res["status"],
        "evidence": res.get("evidence", {}),
    }


def run_rubric(rubric: list[dict[str, Any]], ctx: Ctx) -> dict[str, Any]:
    """Return {checklist, violations, advisories, review_needed}. Each checklist row:
    {id, primitive, tier, applies_to_paths, status ∈ {met,not_met,indeterminate,na}, evidence}.

    Resolver-first (Slice 3): `deal_detect`/`path_select` run BEFORE the rest (regardless of list order) and
    write deal/consent/path onto ctx, so `conditional_on` + `applies_to_paths` resolve against real state.
    Each entry executes exactly once."""
    rubric = rubric or []
    resolved: dict[str, dict[str, Any]] = {}
    for entry in rubric:
        if str(entry.get("primitive")) in RESOLVER_PRIMITIVES:
            res = run_primitive(str(entry.get("primitive")), entry, ctx)
            ev = res.get("evidence") or {}
            if "deal" in ev:
                ctx["deal"] = ev["deal"]; ctx["consent"] = ev.get("consent")
            if "path" in ev:
                ctx["path"] = ev["path"]; ctx["service"] = ev.get("service")
            resolved[str(entry.get("id"))] = _row(entry, res)

    checklist: list[dict[str, Any]] = []
    for entry in rubric:
        eid = str(entry.get("id", ""))
        if eid in resolved:
            row = resolved[eid]  # already executed in the resolver pass — no double-execution
        else:
            paths = list(entry.get("applies_to_paths") or [])
            if paths:
                cur = ctx.get("path")
                if cur is None:
                    # Fail-closed: the path is unresolved (deterministic mode / no judge / judge omitted
                    # is_titular), so whether this path-gated row applies is UNKNOWN. Never run it blindly
                    # for everyone (that would fail-OPEN — a spurious pass or violation on an out-of-scope
                    # call) → indeterminate → review_needed, matching path_select's own disposition.
                    row = _row(entry, {"status": "indeterminate", "evidence": {"reason": "path unresolved"}})
                elif cur not in paths:
                    row = _row(entry, {"status": "na", "evidence": {"reason": f"path {cur} not in scope"}})
                else:
                    row = _row(entry, run_primitive(str(entry.get("primitive", "")), entry, ctx))
            else:
                row = _row(entry, run_primitive(str(entry.get("primitive", "")), entry, ctx))
        checklist.append(row)

    violations = [r for r in checklist if r["tier"] == "hard" and r["status"] == "not_met"]
    advisories = [r for r in checklist if r["tier"] == "soft"]
    review_needed = [r for r in checklist if r["status"] == "indeterminate"]
    return {"checklist": checklist, "violations": violations,
            "advisories": advisories, "review_needed": review_needed}
