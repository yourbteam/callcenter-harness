"""Per-client profile + per-language pack loading (Slice 1: the harness becomes config-driven).

A client's script/rules live in `profiles/<client>.json`; locale data (number-words, PII cues, NER
labels, STT model+language, recognizer toggles) lives in `languages/<lang>.json`. The engine ships only
generic mechanics; A1 is tenant #1. Fail-closed (NFR-6): a missing/invalid/partial/incompatible config
raises `ConfigError`, which the caller turns into a HOLD — never a silent default.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA = 1
MODELS_ROOT = Path(os.path.expanduser("~/.callcenter-harness/models"))

PROFILE_REQUIRED = ("schema_version", "client_key", "language", "agent_markers", "offer_category_id", "contract")
LANG_REQUIRED = ("schema_version", "number_words", "number_connector", "context_lead_ins", "ner_labels",
                 "stt_model", "stt_language", "recognizers")


class ConfigError(Exception):
    """Raised on any missing/invalid/partial/incompatible profile or language pack (fail-closed → HOLD)."""


@dataclass(frozen=True)
class Profile:
    schema_version: int
    client_key: str
    language: str
    agent_markers: list[str]
    offer_category_id: str
    contract: dict[str, Any]
    call_path: str = "default"
    # Slice 2: the client's scoring rubric (typed checks) + supporting DATA. Optional (a profile with no
    # rubric still runs Slice-1 scoring). `field(default_factory)` — mutable defaults on a frozen dataclass.
    rubric: list[dict[str, Any]] = field(default_factory=list)
    call_paths: list[dict[str, Any]] = field(default_factory=list)
    service_branches: dict[str, Any] = field(default_factory=dict)
    legal_variants: list[dict[str, Any]] = field(default_factory=list)
    # Client/brand STT priming as NATURAL PROSE (a plausible transcript sentence naming the brand/products)
    # fed to faster-whisper initial_prompt. Must be prose, NOT a keyword list — Whisper echoes bare term
    # lists back as output. Optional.
    stt_prompt: str = ""


@dataclass(frozen=True)
class Lang:
    schema_version: int
    number_words: frozenset[str]
    number_connector: str
    context_lead_ins: list[str]
    ner_labels: list[str]
    stt_model_dir: str  # resolved absolute path
    stt_language: str
    egn: bool
    iban_prefix: str
    # Generic locale/domain STT priming as NATURAL PROSE (telco-call sentence) for faster-whisper
    # initial_prompt. Prose, NOT a keyword list (Whisper echoes bare lists). Optional.
    stt_prompt: str = ""


def _read_json(path: Path, what: str) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"{what} not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ConfigError(f"{what} unreadable/invalid JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{what} must be a JSON object: {path}")
    return data


def _require(data: dict[str, Any], keys: tuple[str, ...], what: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise ConfigError(f"{what} missing required key(s): {missing}")
    ver = data.get("schema_version")
    if ver != SUPPORTED_SCHEMA:
        raise ConfigError(f"{what} unsupported schema_version {ver!r} (engine supports {SUPPORTED_SCHEMA})")


def _stt_prompt_str(data: dict[str, Any], what: str) -> str:
    """Read optional `stt_prompt`, fail-closed if present but not a string. It must be PROSE — a list/number
    coerced via str() would feed a bracketed keyword-list to Whisper and revive the prompt-echo bug."""
    val = data.get("stt_prompt")
    if val is None:
        return ""
    if not isinstance(val, str):
        raise ConfigError(f"{what}: `stt_prompt` must be a prose string, not {type(val).__name__} "
                          "(a keyword list makes STT echo the terms back)")
    return val


def load_profile(path: str) -> Profile:
    data = _read_json(Path(path), "profile")
    _require(data, PROFILE_REQUIRED, "profile")
    if not isinstance(data["contract"], dict) or not data["agent_markers"]:
        raise ConfigError("profile: `contract` must be an object and `agent_markers` non-empty")
    rubric = data.get("rubric") or []
    if not isinstance(rubric, list):
        raise ConfigError("profile: `rubric` must be a list")
    for i, entry in enumerate(rubric):  # fail-closed on a malformed rubric check (M3 §11)
        if not isinstance(entry, dict) or not entry.get("id") or not entry.get("primitive"):
            raise ConfigError(f"profile: rubric[{i}] must have `id` and `primitive`")
        if entry.get("tier") not in ("hard", "soft"):
            raise ConfigError(f"profile: rubric[{i}] `tier` must be 'hard' or 'soft'")
    return Profile(
        schema_version=int(data["schema_version"]),
        client_key=str(data["client_key"]),
        language=str(data["language"]),
        agent_markers=list(data["agent_markers"]),
        offer_category_id=str(data["offer_category_id"]),
        contract=dict(data["contract"]),
        call_path=str(data.get("call_path") or "default"),
        rubric=list(rubric),
        call_paths=list(data.get("call_paths") or []),
        service_branches=dict(data.get("service_branches") or {}),
        legal_variants=list(data.get("legal_variants") or []),
        stt_prompt=_stt_prompt_str(data, "profile"),
    )


def load_language(key: str, languages_dir: str = "languages", models_root: Path = MODELS_ROOT) -> Lang:
    data = _read_json(Path(languages_dir) / f"{key}.json", f"language pack '{key}'")
    _require(data, LANG_REQUIRED, f"language pack '{key}'")
    rec = data["recognizers"]
    if not isinstance(rec, dict) or "egn" not in rec or "iban_prefix" not in rec:
        raise ConfigError(f"language pack '{key}': recognizers must include egn + iban_prefix")
    # Resolve the STT model NAME to its vendored directory (parity: a bare name is not a usable model_dir).
    stt_model_dir = str(models_root / str(data["stt_model"]))
    return Lang(
        schema_version=int(data["schema_version"]),
        number_words=frozenset(data["number_words"]),
        number_connector=str(data["number_connector"]),
        context_lead_ins=list(data["context_lead_ins"]),
        ner_labels=list(data["ner_labels"]),
        stt_model_dir=stt_model_dir,
        stt_language=str(data["stt_language"]),
        egn=bool(rec["egn"]),
        iban_prefix=str(rec["iban_prefix"]),
        stt_prompt=_stt_prompt_str(data, f"language pack '{key}'"),
    )
