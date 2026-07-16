"""Interleaved, role-labeled dialogue transcript (Caller vs Client) from the per-channel eval transcript.

Stereo calls are split L/R and the classifier assigns an agent channel + a customer channel, each stored
with word-level timestamps. This merges both channels' words into ONE chronological back-and-forth, grouped
into speaker turns and labeled by ROLE (labels come from config — the engine stays hollow). It is PII-free:
turns are labeled by role only, never by name (names remain masked by the redaction stage).

Mono calls have no channel separation, so no speaker split is possible — they render as a single unlabeled
block with a note (decision: stereo-only for now).
"""
from __future__ import annotations

from typing import Any


def _turn_text(words: list[dict[str, Any]]) -> str:
    return "".join(w.get("word", "") for w in words).strip()


def build_dialogue(channels: dict[str, Any], agent_channel: str | None, customer_channel: str | None,
                   role_labels: dict[str, Any]) -> dict[str, Any]:
    """Return {mono: bool, turns: [{role, label, start, text}]}.

    `channels` = transcription.channels ({chan: {text, words, duration}}). `role_labels` supplies the BG
    labels {agent, customer, unknown, mono_note}. A turn = consecutive words from the same speaker once all
    words are merged and sorted by start time.
    """
    labels = role_labels or {}
    ag_rows = ((channels.get(agent_channel) or {}).get("words")) or [] if agent_channel else []
    cu_rows = ((channels.get(customer_channel) or {}).get("words")) or [] if customer_channel else []

    # Mono / single-speaker: no separation possible → one unlabeled block.
    if not customer_channel or not cu_rows or not ag_rows:
        # pick whichever channel actually has text (agent, else the single mono channel)
        only = (channels.get(agent_channel) or {}) if agent_channel else {}
        if not (only.get("text") or "").strip():
            for ch in channels.values():
                if (ch.get("text") or "").strip():
                    only = ch
                    break
        return {"mono": True, "note": str(labels.get("mono_note") or ""),
                "turns": [{"role": "mono", "label": None, "start": 0.0, "text": (only.get("text") or "").strip()}]
                if (only.get("text") or "").strip() else []}

    # Stereo: tag each word with its role, merge, sort by start, group consecutive same-role words into turns.
    tagged: list[tuple[float, str, dict[str, Any]]] = []
    for w in ag_rows:
        tagged.append((float(w.get("start") or 0.0), "agent", w))
    for w in cu_rows:
        tagged.append((float(w.get("start") or 0.0), "customer", w))
    tagged.sort(key=lambda t: t[0])

    role_label = {"agent": str(labels.get("agent") or "agent"),
                  "customer": str(labels.get("customer") or "customer")}
    turns: list[dict[str, Any]] = []
    cur_role: str | None = None
    cur_words: list[dict[str, Any]] = []
    cur_start = 0.0
    for start, role, w in tagged:
        if role != cur_role:
            if cur_words:
                text = _turn_text(cur_words)
                if text:
                    turns.append({"role": cur_role, "label": role_label[cur_role], "start": cur_start, "text": text})
            cur_role, cur_words, cur_start = role, [w], start
        else:
            cur_words.append(w)
    if cur_words:  # flush last turn
        text = _turn_text(cur_words)
        if text:
            turns.append({"role": cur_role, "label": role_label[cur_role], "start": cur_start, "text": text})
    return {"mono": False, "note": "", "turns": turns}


def render_dialogue(dialogue: dict[str, Any]) -> str:
    """Render the dialogue as text. Role-labeled turns for stereo; a single noted block for mono."""
    turns = dialogue.get("turns") or []
    if dialogue.get("mono"):
        note = dialogue.get("note")
        head = f"[{note}]\n" if note else ""
        return head + (turns[0]["text"] if turns else "")
    width = max((len(t["label"]) for t in turns), default=0)
    lines = []
    for t in turns:
        lines.append(f"{t['label']:<{width}} : {t['text']}")
    return "\n".join(lines)
