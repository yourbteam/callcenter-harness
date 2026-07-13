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


def validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate an in-memory contract dict (as absorbed into a client profile). Raises on missing keys."""
    for key in ("contract_key", "id_prefix", "categories_detail"):
        if key not in contract:
            raise ValueError(f"contract missing required key: {key}")
    return contract


def load_contract(path: str) -> dict[str, Any]:
    return validate_contract(json.loads(Path(path).read_text(encoding="utf-8")))


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


# ---- ClientFiles gap checks (G1 ordering, G2 forbidden/phrasing, G4 first-seconds, G5 persistence, G6
# duration). Pure functions over the agent transcript + word timestamps; config-driven via OPTIONAL
# contract blocks (absent block → that check reports `*_na=True`). Additive to the manager summary. ----

def _first_offset(low: str, keywords: list[str]) -> int:
    """Lowest char offset at which any keyword first appears in `low` (already lowercased), else -1."""
    offs = [low.find(kw.lower()) for kw in keywords if kw]
    offs = [o for o in offs if o >= 0]
    return min(offs) if offs else -1


def check_ordering(source_text: str, cat_keywords: dict[str, list[str]],
                   ordering: list[dict[str, str]]) -> dict[str, Any]:
    """G1: a {before, after} pair is a VIOLATION iff both categories appear and `after` precedes
    `before` in the chronological agent transcript. `na` if no pair had both present."""
    low = source_text.lower()
    violations: list[dict[str, Any]] = []
    evaluated = 0
    for pair in ordering or []:
        b, a = pair.get("before"), pair.get("after")
        bo = _first_offset(low, cat_keywords.get(str(b), []))
        ao = _first_offset(low, cat_keywords.get(str(a), []))
        if bo < 0 or ao < 0:
            continue  # one side absent → ordering not applicable to this pair
        evaluated += 1
        if ao < bo:
            violations.append({"before": b, "after": a, "before_at": bo, "after_at": ao})
    return {"ordering_violations": violations, "ordering_ok": (not violations) if evaluated else None,
            "ordering_na": evaluated == 0}


def check_forbidden(source_text: str, forbidden_words: list[str]) -> dict[str, Any]:
    """G2a: forbidden words that appear in the agent transcript (case-insensitive substring)."""
    low = source_text.lower()
    hits = [w for w in (forbidden_words or []) if w and w.lower() in low]
    return {"forbidden_hits": hits, "forbidden_na": not forbidden_words}


def check_required_phrasings(source_text: str, phrasings: list[str]) -> dict[str, Any]:
    """G2b: required exact phrasings missing from the transcript (case-insensitive substring)."""
    low = source_text.lower()
    missing = [p for p in (phrasings or []) if p and p.lower() not in low]
    return {"required_phrasings_missing": missing, "required_phrasings_na": not phrasings}


def first_seconds_engagement(agent_words: list[dict[str, Any]] | None, n: float,
                             min_words: int) -> dict[str, Any]:
    """G4: number of agent words spoken in the first `n` seconds; flag if below `min_words`. `na` if no
    word timestamps are available."""
    if not agent_words:
        return {"first_seconds_words": None, "first_seconds_flag": None, "first_seconds_na": True}
    count = sum(1 for w in agent_words
                if (w.get("word") or "").strip() and float(w.get("start") or 0.0) < n)
    return {"first_seconds_words": count, "first_seconds_flag": count < min_words, "first_seconds_na": False}


def persistence(source_text: str, offer_keywords: list[str],
                ask_phrases: list[str]) -> dict[str, Any]:
    """G5: did the agent repeat the offer and ask for a decision? `offer_repeats` = offer-keyword hits
    beyond the first; `ask_for_decision_count` = ask-phrase hits; flag if the agent never asked."""
    low = source_text.lower()
    offer_hits = sum(low.count(kw.lower()) for kw in (offer_keywords or []) if kw)
    ask_count = sum(low.count(p.lower()) for p in (ask_phrases or []) if p)
    na = not offer_keywords and not ask_phrases
    return {"offer_repeats": max(0, offer_hits - 1) if offer_hits else 0,
            "ask_for_decision_count": ask_count,
            "persistence_flag": (ask_count == 0) if not na else None,
            "persistence_na": na}


def gap_checks(contract: dict[str, Any], source_text: str,
               agent_words: list[dict[str, Any]] | None, duration: float | None,
               offer_category_id: str) -> dict[str, Any]:
    """Aggregate the deterministic ClientFiles gap checks into additive manager-summary fields. All
    driven by OPTIONAL contract blocks; a missing block yields a `*_na` for that check.
    `offer_category_id` (the client's offer category) comes from the profile — not hardcoded."""
    cat_kw = {str(d["category"]): [str(k) for k in d.get("keywords", [])]
              for d in contract.get("categories_detail", [])}
    fs = contract.get("first_seconds") or {}
    out: dict[str, Any] = {"duration_seconds": round(float(duration), 1) if duration else None}
    out.update(check_ordering(source_text, cat_kw, contract.get("ordering") or []))
    out.update(check_forbidden(source_text, contract.get("forbidden_words") or []))
    out.update(check_required_phrasings(source_text, contract.get("required_phrasings") or []))
    out.update(first_seconds_engagement(agent_words, float(fs.get("n", 10)), int(fs.get("min_words", 12))))
    out.update(persistence(source_text, cat_kw.get(offer_category_id, []),
                           contract.get("ask_for_decision_phrases") or []))
    return out


def evaluate(contract: dict[str, Any], source_text: str, *,
             agent_words: list[dict[str, Any]] | None = None,
             duration: float | None = None, offer_category_id: str = "") -> EvalResult:
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
    summary.update(gap_checks(contract, source_text, agent_words, duration, offer_category_id))  # G1/G2/G4/G5/G6 (additive)
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


# ---- Command-backed (model-judged) evaluation ------------------------------------------------------

def _parse_present(value: Any, category: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    raise ValueError(f"category '{category}' has invalid 'present': {value!r}")


def _parse_conveyed(value: Any, category: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"category '{category}' has invalid 'conveyed': {value!r}")
    if not 0.0 <= f <= 1.0:
        raise ValueError(f"category '{category}' 'conveyed' out of [0,1]: {f}")
    return f


def _parse_score(obj: Any, name: str) -> float:
    if not isinstance(obj, dict):
        raise ValueError(f"judge output missing '{name}' object")
    try:
        s = float(obj.get("score"))
    except (TypeError, ValueError):
        raise ValueError(f"'{name}.score' is not numeric: {obj.get('score')!r}")
    if not 0.0 <= s <= 1.0:
        raise ValueError(f"'{name}.score' out of [0,1]: {s}")
    return s


def _parse_objection(payload: dict[str, Any]) -> dict[str, Any]:
    """G3: OPTIONAL objection object. Absent (e.g. the deterministic fixture judge) → `na`. Present but
    not a well-formed dict with bool raised/rebutted → raise (HOLD, G8)."""
    obj = payload.get("objection")
    if obj is None:
        return {"objection_raised": "na", "objection_rebutted": "na"}
    if not isinstance(obj, dict):
        raise ValueError(f"judge 'objection' must be an object, got {type(obj).__name__}")
    return {"objection_raised": _parse_present(obj.get("raised"), "objection.raised"),
            "objection_rebutted": _parse_present(obj.get("rebutted"), "objection.rebutted")}


def evaluate_command(
    contract: dict[str, Any], source_text: str, prosody_summary: str, executor: Any, *,
    agent_words: list[dict[str, Any]] | None = None, duration: float | None = None,
    customer_text: str | None = None, conveyed_threshold: float = 0.5,
    offer_category_id: str = "",
) -> EvalResult:
    """Model-judged script adherence + emotion + active listening (+ optional objection). The executor
    runs the configured model command; its JSON is validated strictly (G8 — malformed output raises, the
    phase then HOLDs). A mandatory element counts as met only if the model marks it present AND
    conveyed >= threshold."""
    from cc_harness.phase_ledger.prompts import judge_prompt

    payload = executor.run_role("judge", judge_prompt(contract, source_text, prosody_summary, customer_text or ""))
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ValueError("judge output missing 'elements' array")
    by_cat: dict[str, dict[str, Any]] = {str(e.get("category")): e for e in elements if isinstance(e, dict)}

    items: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    quote_total = quote_exact = 0
    for idx, detail in enumerate(contract["categories_detail"], start=1):
        category = str(detail["category"])
        mandatory = int(detail.get("minimum_count", 0)) > 0
        # Strict validation (G8 / NFR-5): a dropped category or a garbled field is malformed output →
        # RAISE (the phase HOLDs) rather than defaulting to a fabricated fail-score.
        if category not in by_cat:
            raise ValueError(f"judge omitted contract category '{category}'")
        ent = by_cat[category]
        present = _parse_present(ent.get("present"), category)
        conveyed = _parse_conveyed(ent.get("conveyed"), category)
        evidence = str(ent.get("evidence") or "").strip()
        met = present and conveyed >= conveyed_threshold
        if met:
            # A "met" element MUST be backed by an exact source quote (auditability) — else it is an
            # unbacked/hallucinated judgment → HOLD.
            if not evidence or evidence not in source_text:
                raise ValueError(f"category '{category}' scored met but evidence is not an exact source quote")
        if evidence:
            quote_total += 1
            if evidence in source_text:
                quote_exact += 1
        items.append({"id": f"{contract['id_prefix']}-{idx:03d}", "category": category,
                      "mandatory": mandatory, "matched": met, "conveyed": round(conveyed, 2),
                      "source_quote": [evidence] if evidence else []})
        if mandatory and not met:
            findings.append({"id": f"missing-{category}", "category": category,
                             "problem": f"Mandatory element '{category}' not conveyed (present={present}, conveyed={conveyed})."})

    mand = [i for i in items if i["mandatory"]]
    emotion_score = _parse_score(payload.get("emotion"), "emotion")
    active_score = _parse_score(payload.get("active_listening"), "active_listening")
    emotion = payload.get("emotion") or {}
    active = payload.get("active_listening") or {}
    summary = {
        "mode": "command",
        "item_count": len(items),
        "mandatory_count": len(mand),
        "matched_mandatory": sum(1 for i in mand if i["matched"]),
        "finding_count": len(findings),
        "adherence_score": round(sum(1 for i in mand if i["matched"]) / len(mand), 3) if mand else 0.0,
        "emotion_score": emotion_score,
        "active_listening_score": active_score,
        # Every "met" element is quote-backed (enforced above), so coverage is authoritative here.
        "exact_source_quote_coverage": (quote_exact == quote_total) if quote_total else True,
        "category_status": {i["category"]: i["matched"] for i in items},
    }
    lines = [f"# Model-Judged Evaluation — {contract['contract_key']}", "",
             f"- Adherence: {summary['adherence_score']} ({summary['matched_mandatory']}/{summary['mandatory_count']} mandatory conveyed)",
             f"- Emotion: {summary['emotion_score']} — {emotion.get('assessment','')}",
             f"- Active listening: {summary['active_listening_score']} — {active.get('assessment','')}",
             f"- Exact source-quote coverage: {summary['exact_source_quote_coverage']}", ""]
    for it in items:
        lines.append(f"- {'✅' if it['matched'] else '❌'} `{it['id']}` {it['category']} (conveyed={it['conveyed']})")
    summary.update(gap_checks(contract, source_text, agent_words, duration, offer_category_id))  # G1/G2/G4/G5/G6 (additive)
    summary.update(_parse_objection(payload))  # G3 (optional; na if judge omits it)
    ledger = {"contract_key": contract["contract_key"],
              "status": "completed" if not findings else "findings",
              "items": items, "findings": findings, "manager_summary": summary}
    return EvalResult(ledger=ledger, output_text="\n".join(lines))


# ---- Intonation / delivery (deterministic proxy over the prosody summary) --------------------------
import re  # noqa: E402


def evaluate_prosody(
    summary_lines: list[str], speaker: str, min_energy_db: float = 55.0,
    min_pace_wps: float = 1.5, max_pace_wps: float = 4.5, min_pitch_std_hz: float = 15.0,
) -> dict[str, Any]:
    """Deterministic delivery flags from the prosody summary for one speaker (the agent). Flags
    sluggish/low-energy and off-band pace — a first proxy for the intonation dimension + the named
    'sluggish delivery' failure pattern (FirstWorkflow L17). Thresholds are configurable and need
    calibration on the labeled set; nuanced scoring is left to command-backed model roles."""
    energies, paces, pitches = [], [], []
    for ln in summary_lines:
        if not ln.startswith(f"{speaker} "):
            continue
        e = re.search(r"energy=(-?\d+(?:\.\d+)?)dB", ln)
        p = re.search(r"pace=(-?\d+(?:\.\d+)?)wps", ln)
        f0 = re.search(r"pitch=(\d+)Hz", ln)
        if e:
            energies.append(float(e.group(1)))
        if p:
            paces.append(float(p.group(1)))
        if f0 and float(f0.group(1)) > 0:  # voiced turns only
            pitches.append(float(f0.group(1)))
    mean_energy = sum(energies) / len(energies) if energies else 0.0
    mean_pace = sum(paces) / len(paces) if paces else 0.0
    mean_pitch = sum(pitches) / len(pitches) if pitches else 0.0
    # Intonation (T1): pitch VARIATION across voiced turns; a monotone agent has low spread.
    if len(pitches) >= 2:
        _m = mean_pitch
        pitch_std: float | None = (sum((x - _m) ** 2 for x in pitches) / len(pitches)) ** 0.5
    else:
        pitch_std = None  # too few voiced turns to judge intonation
    flags = []
    if energies and mean_energy < min_energy_db:
        flags.append("low_energy_delivery")
    if paces and mean_pace < min_pace_wps:
        flags.append("slow_pace")
    if paces and mean_pace > max_pace_wps:
        flags.append("fast_pace")
    if pitch_std is not None and pitch_std < min_pitch_std_hz:
        flags.append("monotone_delivery")
    return {
        "speaker": speaker,
        "turns": len(paces),
        "mean_energy_db": round(mean_energy, 1),
        "mean_pace_wps": round(mean_pace, 2),
        "mean_pitch_hz": round(mean_pitch, 0),
        "pitch_std_hz": round(pitch_std, 1) if pitch_std is not None else None,
        "pitch_na": pitch_std is None,
        "flags": flags,
    }
