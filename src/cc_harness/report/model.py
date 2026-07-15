"""Build the human-readable scorecard REPORT MODEL from a run's evaluation context.

Pure + generic: every Bulgarian label/section-title/coaching line comes from the `presentation` dict
(profile `scorecard_presentation`); status words/icons come from `status_labels` (language pack). Nothing
locale-specific is hardcoded here — the engine stays hollow. The output is a plain dict a renderer (text,
HTML, or a UI) can consume; the JSON model is the reusable layer (decision D1).

Counting rule (research §4.A, verified): HARD rows with status==na are excluded from the denominator; a
HARD row in review is counted as review, NOT met; advisories = SOFT rows displayed with the ⚠️ icon
(soft not_met, soft indeterminate, or the tone row overridden by a prosody flag).
"""
from __future__ import annotations

from typing import Any


def _mmss(seconds: float | None) -> str:
    if not seconds or seconds <= 0:
        return "—"
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def _display_kind(row: dict[str, Any], tone_criterion: str | None, prosody_flags: list) -> str:
    """Map a checklist row's (tier, status) → display kind: met | violation | review | advisory | na.

    A SOFT failure is an advisory, never a red violation. The tone criterion is downgraded to an advisory
    when the judge passed it but prosody flagged the delivery (mixed signal) — research §4.C / §5.
    """
    tier, status = row.get("tier"), row.get("status")
    if status == "na":
        return "na"
    if status == "met":
        if row.get("id") == tone_criterion and prosody_flags:
            return "advisory"  # mixed signal: judge-positive but prosody flagged
        return "met"
    if status == "not_met":
        return "violation" if tier == "hard" else "advisory"
    if status == "indeterminate":
        return "review" if tier == "hard" else "advisory"
    return "review"  # unknown status → surface for review, never silently drop


def _evidence_text(evidence: Any) -> str:
    """Best human-facing snippet from a row's evidence dict (quote > amounts > phrase), else ''."""
    if not isinstance(evidence, dict):
        return ""
    if evidence.get("quote"):
        return str(evidence["quote"])
    if evidence.get("amounts"):
        return ", ".join(str(a) for a in evidence["amounts"])
    logi = evidence.get("logistics")
    if isinstance(logi, dict) and logi.get("phrase"):
        return str(logi["phrase"])
    for k in ("phrase", "customer_evidence", "evidence"):
        if evidence.get(k):
            return str(evidence[k])
    return ""


def _disposition(context: dict[str, Any], status: str | None, labels: dict[str, Any]) -> tuple[str, str] | None:
    """Return (disposition_text, reason) when the call is NOT fully evaluated, else None.

    Skipped (non-conversation) and held (low-confidence / judge failure) calls get a header + reason and no
    checklist — research §4.A, FR-1.2 / FR-2.3 / NFR-4.
    """
    ingest = context.get("ingest") or {}
    if status == "skipped" or ingest.get("skipped"):
        return (str((labels.get("disposition") or {}).get("skipped") or "skipped"),
                str(ingest.get("reason") or ""))
    ev = context.get("evaluation") or {}
    if status == "blocked" or ev.get("held"):
        reason = ev.get("reason")
        if not reason:
            for key in ("redaction", "transcription"):
                blk = context.get(key) or {}
                if isinstance(blk, dict) and blk.get("held"):
                    reason = blk.get("reason")
                    break
        return (str((labels.get("disposition") or {}).get("held") or "held"), str(reason or ""))
    return None


def build_report_model(context: dict[str, Any], status: str | None, presentation: dict[str, Any],
                       status_labels: dict[str, Any], call_id: str = "") -> dict[str, Any]:
    """Assemble the report model. `presentation` = profile.scorecard_presentation; `status_labels` = lang."""
    presentation = presentation or {}
    status_labels = status_labels or {}
    crit_cfg: dict[str, Any] = presentation.get("criteria") or {}
    sections_cfg: list = presentation.get("sections") or []
    tone_criterion = presentation.get("tone_criterion")

    ingest = context.get("ingest") or {}
    ev = context.get("evaluation") or {}
    checklist: list = ev.get("checklist") or []
    by_id = {r.get("id"): r for r in checklist}
    prosody_flags = ((ev.get("intonation") or {}).get("flags")) or []

    # Header: duration + path + outcome (deal) are read from their real homes.
    deal_ev = (by_id.get("deal") or {}).get("evidence") or {}
    path_ev = (by_id.get("path") or {}).get("evidence") or {}
    is_deal = deal_ev.get("deal") == "deal"
    deal_reason = ""
    if isinstance(deal_ev.get("logistics"), dict):
        deal_reason = str(deal_ev["logistics"].get("phrase") or "")
    elif deal_ev.get("accept_quote"):
        deal_reason = str(deal_ev["accept_quote"])
    header = {
        "call_id": call_id,
        "duration_mmss": _mmss(ingest.get("duration_seconds")),
        "path": path_ev.get("path"),
        "outcome": {"deal": bool(is_deal), "reason": deal_reason,
                    "confidence": "heuristic" if (is_deal and not deal_ev.get("accept_quote")) else "direct"},
    }

    # Disposition gate: skipped / held → header only, no checklist.
    disp = _disposition(context, status, status_labels)
    if disp is not None:
        header["disposition"], header["disposition_reason"] = disp
        return {"header": header, "summary": {}, "sections": [], "coaching": []}
    header["disposition"] = str((status_labels.get("disposition") or {}).get("evaluated") or "evaluated")
    header["disposition_reason"] = ""

    # Rows → sections (grouped + ordered per presentation), skipping the header-only deal/path meta rows.
    meta_ids = {"deal", "path"}
    rows_by_section: dict[str, list] = {}
    for row in checklist:
        cid = row.get("id")
        if cid in meta_ids:
            continue
        cfg = crit_cfg.get(cid) or {}
        kind = _display_kind(row, tone_criterion, prosody_flags)
        entry = {
            "id": cid,
            "label": cfg.get("label") or cid,
            "status": row.get("status"),
            "status_kind": kind,
            "evidence": _evidence_text(row.get("evidence")),
            "proxy_note": cfg.get("proxy_note") or "",
        }
        rows_by_section.setdefault(cfg.get("section") or "other", []).append(entry)

    ordered = sorted(sections_cfg, key=lambda s: s.get("order", 999))
    sections = []
    for sc in ordered:
        sid = sc.get("id")
        rows = rows_by_section.pop(sid, [])
        if rows:
            sections.append({"id": sid, "title": sc.get("title") or sid, "rows": rows})
    for sid, rows in rows_by_section.items():  # any un-configured section, appended last (never dropped)
        sections.append({"id": sid, "title": sid, "rows": rows})

    # Summary counts (the verified rule).
    hard = [r for r in checklist if r.get("tier") == "hard" and r.get("id") not in meta_ids]
    hard_total = sum(1 for r in hard if r.get("status") != "na")
    hard_met = sum(1 for r in hard if r.get("status") == "met")
    hard_viol = sum(1 for r in hard if r.get("status") == "not_met")
    # review absorbs indeterminate AND any out-of-contract status, so met+viol+review==hard_total always
    # holds (and an unknown status is surfaced for review, never silently dropped from the summary).
    hard_review = sum(1 for r in hard if r.get("status") not in ("met", "not_met", "na"))
    advisories = sum(1 for sec in sections for r in sec["rows"] if r["status_kind"] == "advisory")
    summary = {"hard_total": hard_total, "hard_met": hard_met, "hard_violations": hard_viol,
               "hard_review": hard_review, "advisories": advisories}

    # Coaching (generic selection of config-provided BG templates; never hardcoded prose).
    ctpl = presentation.get("coaching") or {}
    coaching: list[str] = []
    if hard_viol and ctpl.get("has_violations"):
        names = ", ".join(r["label"] for sec in sections for r in sec["rows"] if r["status_kind"] == "violation")
        coaching.append(str(ctpl["has_violations"]).replace("{items}", names))
    weak_key = "weak_listening" if any(
        r["status_kind"] == "advisory" and r["id"] in (presentation.get("listening_criteria") or [])
        for sec in sections for r in sec["rows"]) else None
    if weak_key and ctpl.get(weak_key):
        coaching.append(str(ctpl[weak_key]))
    outcome_key = "sale" if is_deal else "no_sale"
    if ctpl.get(outcome_key):
        coaching.append(str(ctpl[outcome_key]))

    return {"header": header, "summary": summary, "sections": sections, "coaching": coaching}
