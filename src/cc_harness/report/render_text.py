"""Render a report model (from model.build_report_model) as a plain-text scorecard box.

Generic: every visible word (icons, status words, and the header/section chrome) comes from `status_labels`
(the language pack) — no locale literals here, so the engine stays hollow. If a label is missing, a neutral
ASCII fallback is used so the renderer never crashes.
"""
from __future__ import annotations

from typing import Any

_BAR = "─" * 60


def _ui(labels: dict[str, Any], key: str, default: str) -> str:
    return str((labels.get("ui") or {}).get(key) or default)


def _mark(labels: dict[str, Any], kind: str) -> tuple[str, str]:
    """(icon, word) for a display kind, from status_labels. Falls back to ASCII."""
    m = labels.get(kind) or {}
    fallback = {"met": ("[ok]", "met"), "violation": ("[X]", "violation"), "review": ("[?]", "review"),
                "na": ("[-]", "n/a"), "advisory": ("[!]", "advisory")}.get(kind, ("[ ]", kind))
    return str(m.get("icon") or fallback[0]), str(m.get("word") or fallback[1])


def render_text(model: dict[str, Any], status_labels: dict[str, Any]) -> str:
    labels = status_labels or {}
    h = model.get("header") or {}
    out: list[str] = [_BAR]

    # Header line
    parts = [f"{_ui(labels, 'call', 'CALL')}: {h.get('call_id') or '—'}"]
    if h.get("duration_mmss"):
        parts.append(str(h["duration_mmss"]))
    if h.get("path"):
        parts.append(f"{_ui(labels, 'type', 'Type')}: {h['path']}")
    if h.get("disposition"):
        parts.append(f"{_ui(labels, 'state', 'State')}: {h['disposition']}")
    out.append("  " + " · ".join(parts))
    if h.get("disposition_reason"):
        out.append(f"  ({h['disposition_reason']})")

    # Outcome — only for fully-evaluated calls; a held/skipped call's outcome is UNKNOWN, not "no sale"
    outcome = h.get("outcome") or {}
    if "deal" in outcome and model.get("summary"):
        icon = _ui(labels, "deal_icon", "*") if outcome.get("deal") else _ui(labels, "no_deal_icon", "o")
        word = _ui(labels, "sale", "SALE") if outcome.get("deal") else _ui(labels, "no_sale", "No sale")
        line = f"  {_ui(labels, 'result', 'RESULT')}: {icon} {word}"
        if outcome.get("reason"):
            line += f"  ({outcome['reason']})"
        out.append(line)

    # Summary (only for fully-evaluated calls)
    s = model.get("summary") or {}
    if s:
        out.append("  " + _ui(labels, "summary", "Summary") + ": "
                   + f"{_ui(labels, 'mandatory', 'Mandatory')} {s.get('hard_met', 0)}/{s.get('hard_total', 0)}"
                   + f" · {s.get('hard_violations', 0)} {_ui(labels, 'violations_word', 'violations')}"
                   + f" · {_mark(labels, 'review')[0]} {s.get('hard_review', 0)} {_ui(labels, 'review_word', 'review')}"
                   + f" · {_ui(labels, 'advisories_word', 'advisories')}: {s.get('advisories', 0)}")
    out.append(_BAR)

    # Sections
    for sec in model.get("sections") or []:
        out.append("  " + str(sec.get("title") or sec.get("id")).upper())
        for r in sec.get("rows") or []:
            icon, _word = _mark(labels, r.get("status_kind") or "review")
            line = f"     {icon} {r.get('label') or r.get('id')}"
            ev = r.get("evidence")
            if ev:
                line += f"   «{ev[:80]}»"
            if r.get("proxy_note"):
                line += f"  ({r['proxy_note']})"
            out.append(line)

    # Coaching
    coaching = model.get("coaching") or []
    if coaching:
        out.append("  " + _ui(labels, "coaching_title", "NOTES").upper())
        for line in coaching:
            out.append(f"     {line}")
    out.append(_BAR)
    return "\n".join(out)
