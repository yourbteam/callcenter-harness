#!/usr/bin/env python3
"""Air-gapped LLM judge adapter for cc_harness command-mode eval (CC_HARNESS_AGENT_COMMAND).

Reads the judge prompt on stdin (built by cc_harness.phase_ledger.prompts.judge_prompt), sends it to a
LOCAL Ollama server on loopback, and prints the judgment JSON on stdout in the exact shape the evaluator
requires (elements[], emotion{score}, active_listening{score}, notes).

Air-gapped (NFR-7): talks ONLY to 127.0.0.1 (Ollama). The model is local; no external egress. Set
NO_PROXY=127.0.0.1 so a dead-proxy air-gap test still reaches loopback.

Fail-closed: any error (server down, bad JSON, oversized prompt) exits nonzero → the harness HOLDs and
never fabricates a score. The executor already retries transient failures up to 3x.

Stdlib only (urllib/json) so it runs under plain python3 — no venv, no pip deps.

Usage (wired via env):
  CC_HARNESS_AGENT_COMMAND="python3 /abs/path/scripts/judge_ollama.py --model qwen2.5:32b"
Config env: JUDGE_MODEL, OLLAMA_HOST (default http://127.0.0.1:11434), JUDGE_NUM_CTX (default 8192),
            JUDGE_TIMEOUT_SECONDS (default 170).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

TRANSCRIPT_MARK = "## TRANSCRIPT (redacted, PII-free)\n"
PROSODY_MARK = "\n\n## PROSODY SUMMARY"
CUSTOMER_MARK = "## CUSTOMER CHANNEL (redacted, PII-free)\n"
OUTPUT_MARK = "\n\nOUTPUT JSON SHAPE:"
CONVEYED_THRESHOLD = 0.5


def die(msg: str) -> "None":
    print(f"judge_ollama: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _extract_source_text(prompt: str) -> str:
    """Recover the transcript the model must quote from, using prompts.py's exact markers."""
    if TRANSCRIPT_MARK not in prompt:
        return ""
    tail = prompt.split(TRANSCRIPT_MARK, 1)[1]
    return tail.split(PROSODY_MARK, 1)[0] if PROSODY_MARK in tail else tail


def _extract_customer_text(prompt: str) -> str:
    """Recover the customer-channel text (for objection-evidence validation), using prompts.py markers."""
    if CUSTOMER_MARK not in prompt:
        return ""
    tail = prompt.split(CUSTOMER_MARK, 1)[1]
    return tail.split(OUTPUT_MARK, 1)[0] if OUTPUT_MARK in tail else tail


def _ollama_chat(host: str, model: str, prompt: str, num_ctx: int, timeout: int) -> str:
    """POST /api/chat with format=json (guaranteed valid JSON) + deterministic options. Returns the
    assistant message content (a JSON string)."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",  # LOCKED baseline: valid-JSON mode (universally supported). Keys guaranteed
                            # by the prompt's OUTPUT_JSON_SHAPE + evaluator validation + executor retries.
        "options": {"temperature": 0, "seed": 0, "num_ctx": num_ctx},
    }).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - loopback only
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - any transport/parse failure is fail-closed
        die(f"ollama call failed ({host}, model={model}): {exc}")
    content = (payload.get("message") or {}).get("content")
    if not isinstance(content, str) or not content.strip():
        die("ollama returned no message content")
    return content


def _to_float(v: object) -> "float | None":
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _is_present(v: object) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return False


def _repair_evidence(judgment: dict, source_text: str, customer_text: str = "") -> dict:
    """Guarantee the evaluator's contract (evaluator.py:188): a MET element (present AND conveyed>=0.5)
    must carry an EXACT source substring as evidence. Repair the model's near-miss quote to an exact
    slice; if no exact span exists, DOWNGRADE (conveyed=0.0) so the element is not 'met' and needs no
    quote. Never fabricate a positive, never emit a met element with non-exact evidence (which would HOLD).
    """
    elements = judgment.get("elements")
    if not isinstance(elements, list):
        return judgment  # let the evaluator raise → executor retries
    for el in elements:
        if not isinstance(el, dict):
            continue
        conveyed = _to_float(el.get("conveyed"))
        met = _is_present(el.get("present")) and conveyed is not None and conveyed >= CONVEYED_THRESHOLD
        if not met:
            continue
        evidence = str(el.get("evidence") or "").strip()
        if evidence and evidence in source_text:
            el["evidence"] = evidence
            continue
        # try case-insensitive locate → replace with the exact source slice
        if evidence:
            idx = source_text.lower().find(evidence.lower())
            if idx >= 0:
                el["evidence"] = source_text[idx: idx + len(evidence)]
                continue
        # no exact span → downgrade to not-met (honest: unaudited quote = not conveyed)
        el["conveyed"] = 0.0
        el["evidence"] = ""
    # G3: objection.evidence must quote the CUSTOMER channel exactly, else blank it (never fabricate).
    obj = judgment.get("objection")
    if isinstance(obj, dict):
        ev = str(obj.get("evidence") or "").strip()
        if ev and ev not in customer_text:
            idx = customer_text.lower().find(ev.lower())
            obj["evidence"] = customer_text[idx: idx + len(ev)] if idx >= 0 else ""
    return judgment


def run_judge(model: str, host: str, num_ctx: int, timeout: int) -> None:
    prompt = sys.stdin.read()
    if not prompt.strip():
        die("empty stdin prompt")
    # RJ12: fail closed rather than let Ollama silently truncate an oversized prompt.
    approx_tokens = len(prompt) / 3.5
    if approx_tokens > num_ctx * 0.9:
        die(f"prompt ~{int(approx_tokens)} tokens exceeds 90% of num_ctx={num_ctx}; raise JUDGE_NUM_CTX")
    content = _ollama_chat(host, model, prompt, num_ctx, timeout)
    try:
        judgment = json.loads(content)
    except json.JSONDecodeError as exc:
        die(f"model did not return valid JSON: {exc}")
    if not isinstance(judgment, dict):
        die("model JSON is not an object")
    judgment = _repair_evidence(judgment, _extract_source_text(prompt), _extract_customer_text(prompt))
    sys.stdout.write(json.dumps(judgment, ensure_ascii=False))


def run_selftest(model: str, host: str, num_ctx: int, timeout: int) -> None:
    """Prove the loopback server answers with JSON (used by setup_airgapped_judge.sh verify)."""
    prompt = sys.stdin.read() or 'Reply with {"ok": true} only.'
    content = _ollama_chat(host, model, prompt, num_ctx, timeout)
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        die(f"selftest: non-JSON reply: {exc}")
    if not isinstance(obj, dict):
        die("selftest: reply not a JSON object")
    print(json.dumps(obj, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("JUDGE_MODEL", "qwen2.5:32b"))
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    num_ctx = int(os.environ.get("JUDGE_NUM_CTX") or 8192)
    timeout = int(os.environ.get("JUDGE_TIMEOUT_SECONDS") or 170)
    if args.selftest:
        run_selftest(args.model, host, num_ctx, timeout)
    else:
        run_judge(args.model, host, num_ctx, timeout)


if __name__ == "__main__":
    main()
