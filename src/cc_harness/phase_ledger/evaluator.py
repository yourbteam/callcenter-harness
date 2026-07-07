"""Deterministic phase-ledger evaluator — script-adherence scoring against a per-branch contract.

Forked from the UP harness deterministic phase-ledger (`up_harness/phase_ledger/manager.py`): a producer
finds a source-quote for each mandatory category, a verifier flags categories that are missing (or below
`minimum_count`), and a manager summary reports the adherence score + exact-source-quote coverage
(NFR-5 auditability). Source quotes are exact substrings of the source text.

M5 scope: script-adherence (keyword-anchored presence of mandatory elements) over the eval transcript.
Intonation/active-listening scoring from the prosody summary needs command-backed model roles (UP's
`execution_mode=command`) and is a later increment — the prosody text is already in the source packet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalResult:
    ledger: dict[str, Any]
    output_text: str


def load_contract(path: str) -> dict[str, Any]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("contract_key", "id_prefix", "categories_detail"):
        if key not in contract:
            raise ValueError(f"contract missing required key: {key}")
    return contract


def _find_quote(source_text: str, keywords: list[str], window: int = 40) -> str | None:
    """Return a BOUNDED exact substring around the first keyword hit (not the whole transcript, so the
    audit quote is specific — NFR-5)."""
    low = source_text.lower()
    for kw in keywords:
        pos = low.find(kw.lower())
        if pos != -1:
            start = max(0, pos - window)
            end = min(len(source_text), pos + len(kw) + window)
            quote = source_text[start:end].strip()
            return quote or source_text[start:end]  # stripped result is still a contiguous substring
    return None


def evaluate(contract: dict[str, Any], source_text: str) -> EvalResult:
    items: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for idx, detail in enumerate(contract["categories_detail"], start=1):
        category = str(detail["category"])
        keywords = [str(k) for k in detail.get("keywords", [])]
        # minimum_count > 0 marks a MANDATORY element (present-or-not); 0 marks an optional one.
        mandatory = int(detail.get("minimum_count", 0)) > 0
        quote = _find_quote(source_text, keywords)
        matched = quote is not None
        items.append({
            "id": f"{contract['id_prefix']}-{idx:03d}",
            "category": category,
            "mandatory": mandatory,
            "matched": matched,
            "source_quote": [quote] if quote else [],
            "detail": f"{category}: {'present' if matched else 'MISSING'}",
        })
        if mandatory and not matched:
            findings.append({
                "id": f"missing-{category}",
                "category": category,
                "problem": f"Mandatory element '{category}' not found in the transcript.",
            })
    # Adherence is scored over MANDATORY elements only (FR-4.2: "mandatory elements said");
    # optional elements (upsells) are reported separately and never drag the score down.
    mandatory_items = [i for i in items if i["mandatory"]]
    total_mandatory = len(mandatory_items)
    matched_mandatory = sum(1 for i in mandatory_items if i["matched"])
    optional_items = [i for i in items if not i["mandatory"]]
    quotes = [q for i in items for q in i["source_quote"]]
    exact = sum(1 for q in quotes if q in source_text)
    summary = {
        "item_count": len(items),
        "mandatory_count": total_mandatory,
        "matched_mandatory": matched_mandatory,
        "optional_present": sum(1 for i in optional_items if i["matched"]),
        "optional_count": len(optional_items),
        "finding_count": len(findings),
        "adherence_score": round(matched_mandatory / total_mandatory, 3) if total_mandatory else 0.0,
        "exact_source_quote_coverage": (exact == len(quotes)) if quotes else False,
        "category_status": {i["category"]: i["matched"] for i in items},
    }
    ledger = {
        "contract_key": contract["contract_key"],
        "status": "completed" if not findings else "findings",
        "items": items,
        "findings": findings,
        "manager_summary": summary,
    }
    return EvalResult(ledger=ledger, output_text=_compose(contract, summary, items, findings))


def _compose(contract: dict[str, Any], summary: dict[str, Any], items: list[dict[str, Any]],
             findings: list[dict[str, Any]]) -> str:
    lines = [f"# Script-Adherence Evaluation — {contract['contract_key']}", ""]
    lines.append(f"- Adherence score: {summary['adherence_score']} "
                 f"({summary['matched_mandatory']}/{summary['mandatory_count']} mandatory elements present)")
    lines.append(f"- Optional elements present: {summary['optional_present']}/{summary['optional_count']}")
    lines.append(f"- Findings (missing mandatory elements): {summary['finding_count']}")
    lines.append(f"- Exact source-quote coverage: {summary['exact_source_quote_coverage']}")
    lines.append("")
    lines.append("## Elements")
    for it in items:
        tag = "mandatory" if it["mandatory"] else "optional"
        lines.append(f"- {'✅' if it['matched'] else '❌'} `{it['id']}` {it['category']} ({tag})")
    if findings:
        lines.append("")
        lines.append("## Missing mandatory")
        for f in findings:
            lines.append(f"- {f['id']}: {f['problem']}")
    return "\n".join(lines)


# ---- Intonation / delivery (deterministic proxy over the prosody summary) --------------------------
import re  # noqa: E402


def evaluate_prosody(
    summary_lines: list[str], speaker: str, min_energy_db: float = 55.0,
    min_pace_wps: float = 1.5, max_pace_wps: float = 4.5,
) -> dict[str, Any]:
    """Deterministic delivery flags from the prosody summary for one speaker (the agent). Flags
    sluggish/low-energy and off-band pace — a first proxy for the intonation dimension + the named
    'sluggish delivery' failure pattern (FirstWorkflow L17). Thresholds are configurable and need
    calibration on the labeled set; nuanced scoring is left to command-backed model roles."""
    energies, paces = [], []
    for ln in summary_lines:
        if not ln.startswith(f"{speaker} "):
            continue
        e = re.search(r"energy=(-?\d+(?:\.\d+)?)dB", ln)
        p = re.search(r"pace=(-?\d+(?:\.\d+)?)wps", ln)
        if e:
            energies.append(float(e.group(1)))
        if p:
            paces.append(float(p.group(1)))
    mean_energy = sum(energies) / len(energies) if energies else 0.0
    mean_pace = sum(paces) / len(paces) if paces else 0.0
    flags = []
    if energies and mean_energy < min_energy_db:
        flags.append("low_energy_delivery")
    if paces and mean_pace < min_pace_wps:
        flags.append("slow_pace")
    if paces and mean_pace > max_pace_wps:
        flags.append("fast_pace")
    return {
        "speaker": speaker,
        "turns": len(paces),
        "mean_energy_db": round(mean_energy, 1),
        "mean_pace_wps": round(mean_pace, 2),
        "flags": flags,
    }
