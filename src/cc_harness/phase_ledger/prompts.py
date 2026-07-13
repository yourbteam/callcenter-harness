"""Judge role prompt for command-backed evaluation.

Builds a single strict prompt from the per-branch contract + the source packet (redacted transcript +
prosody summary). The model judges, per mandatory element, whether it was semantically *conveyed* (not
just keyword-present), plus emotion and active-listening. Markers (`PHASE CONTRACT:` / `SOURCE REQUEST:` /
`OUTPUT JSON SHAPE:`) let a deterministic fixture parse the prompt for tests.
"""

from __future__ import annotations

import json
from typing import Any

OUTPUT_JSON_SHAPE = {
    "elements": [
        {"category": "<category id>", "present": "true|false",
         "conveyed": "0.0-1.0 (how well the mandatory element was actually delivered)",
         "evidence": "<exact quote from SOURCE, or empty>"}
    ],
    "emotion": {"score": "0.0-1.0", "assessment": "<short, on the agent's warmth/confidence>"},
    "active_listening": {"score": "0.0-1.0", "assessment": "<short, did the agent respond to the customer>"},
    "objection": {"raised": "true|false (did the CUSTOMER raise an objection/resistance)",
                  "rebutted": "true|false (did the AGENT rebut it and keep selling, vs drop it)",
                  "evidence": "<exact quote from the CUSTOMER CHANNEL, or empty>"},
    "notes": "<optional short overall note>",
}


RUBRIC_OUTPUT_JSON_SHAPE = {
    "checks": {"<check id>": {"met": "true|false",
                              "evidence": "<exact quote from SOURCE that proves it, or empty>",
                              "detail": "<short reason>"}},
    "deal": {"happened": "true|false (did the customer AGREE and the sale close)",
             "consent": "true|false (explicit consent to proceed / take data)",
             "refusal": "true|false (customer refused)"},
    "path": {"is_titular": "true|false (the interlocutor is the account holder)",
             "decision_maker": "true|false (answered YES to 'do you decide about this service')",
             "service": "mobile|fixed|null"},
    "emotion": {"score": "0.0-1.0 (agent warmth/confidence)"},
    "active_listening": {"score": "0.0-1.0 (did the agent respond to the customer)"},
    "objection": {"raised": "true|false", "rebutted": "true|false",
                  "matched": "true|false (2nd objection matched the 1st → real, not brush-off)",
                  "evidence": "<exact quote from the CUSTOMER CHANNEL, or empty>"},
    "notes": "<optional short overall note>",
}


def judge_prompt_from_rubric(cmd_checks: list[dict[str, Any]], source_text: str, prosody_summary: str,
                             customer_text: str = "") -> str:
    """Slice 3: build the judge prompt from the profile's CMD rubric entries (each {id, question}) — NOT the
    legacy categories_detail. The judge returns a verdict per check id + deal/path/emotion/listening/objection."""
    checks = [{"id": str(c.get("id")), "question": str(c.get("question", "") or c.get("id"))}
              for c in cmd_checks]
    return "\n".join([
        "You are the QA judge for an outbound tele-sales call. Using ONLY the SOURCE REQUEST (a redacted,",
        "PII-free agent transcript + per-turn prosody + the customer channel), answer each CHECK, decide",
        "whether a sale happened (deal), who is on the line (path), score emotion + active listening, and",
        "judge the customer objection and whether the agent rebutted vs dropped it. Quote exact evidence",
        "from SOURCE for every `met` check. Return ONLY the JSON object.",
        "",
        "PHASE CONTRACT:",
        json.dumps({"checks": checks}, ensure_ascii=False),
        "",
        "SOURCE REQUEST:",
        "## TRANSCRIPT (agent, redacted, PII-free)",
        source_text,
        "",
        "## PROSODY SUMMARY (per-turn pitch/pace/energy/pauses)",
        prosody_summary or "(none)",
        "",
        "## CUSTOMER CHANNEL (redacted, PII-free)",
        customer_text or "(none)",
        "",
        "OUTPUT JSON SHAPE:",
        json.dumps(RUBRIC_OUTPUT_JSON_SHAPE, ensure_ascii=False, indent=2),
    ])


def judge_prompt(contract: dict[str, Any], source_text: str, prosody_summary: str,
                 customer_text: str = "") -> str:
    return "\n".join([
        "You are the QA judge for an outbound tele-sales call. Score the AGENT against the mandatory",
        "script elements in the phase contract, using only the SOURCE REQUEST (a redacted, PII-free",
        "transcript plus a per-turn prosody summary and the customer channel). For each contract category",
        "decide if it was semantically CONVEYED (not just whether a keyword appears), quote exact evidence",
        "from SOURCE, score emotion (warmth/confidence) and active listening, and judge whether the",
        "CUSTOMER raised an objection and whether the AGENT rebutted it (kept selling) vs dropped it.",
        "Return ONLY the JSON object.",
        "",
        "PHASE CONTRACT:",
        json.dumps({"contract_key": contract.get("contract_key"),
                    "categories_detail": contract.get("categories_detail", [])}, ensure_ascii=False),
        "",
        "SOURCE REQUEST:",
        "## TRANSCRIPT (redacted, PII-free)",
        source_text,
        "",
        "## PROSODY SUMMARY (per-turn pitch/pace/energy/pauses)",
        prosody_summary or "(none)",
        "",
        "## CUSTOMER CHANNEL (redacted, PII-free)",
        customer_text or "(none)",
        "",
        "OUTPUT JSON SHAPE:",
        json.dumps(OUTPUT_JSON_SHAPE, ensure_ascii=False, indent=2),
    ])
