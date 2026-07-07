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
    "notes": "<optional short overall note>",
}


def judge_prompt(contract: dict[str, Any], source_text: str, prosody_summary: str) -> str:
    return "\n".join([
        "You are the QA judge for an outbound tele-sales call. Score the AGENT against the mandatory",
        "script elements in the phase contract, using only the SOURCE REQUEST (a redacted, PII-free",
        "transcript plus a per-turn prosody summary). For each contract category decide if it was",
        "semantically CONVEYED (not just whether a keyword appears), quote exact evidence from SOURCE,",
        "and score emotion (warmth/confidence) and active listening. Return ONLY the JSON object.",
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
        "OUTPUT JSON SHAPE:",
        json.dumps(OUTPUT_JSON_SHAPE, ensure_ascii=False, indent=2),
    ])
