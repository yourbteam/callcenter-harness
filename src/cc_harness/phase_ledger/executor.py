"""Command-backed role executor for cc_harness evaluation.

Mirrors the UP harness `CommandRoleExecutor` pattern (reference only — no dependency): a configured
external model command reads a role prompt from stdin and returns a JSON object on stdout. The model is
**pluggable** (self-hosted or cloud) via `CC_HARNESS_AGENT_COMMAND` — the harness hardcodes no provider.
It runs on the **redacted, PII-free** transcript, so this does not touch source audio (NFR-7 governs audio).

Fail-closed: if the command is not configured, `from_env` raises — the caller turns that into a HOLD.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

AGENT_COMMAND_ENV = "CC_HARNESS_AGENT_COMMAND"
AGENT_TIMEOUT_ENV = "CC_HARNESS_AGENT_TIMEOUT_SECONDS"


@dataclass(frozen=True)
class CommandRoleExecutor:
    command: list[str]
    timeout_seconds: int = 180
    max_attempts: int = 3
    retry_log: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "CommandRoleExecutor":
        cmd = os.environ.get(AGENT_COMMAND_ENV, "").strip()
        if not cmd:
            raise RuntimeError(f"{AGENT_COMMAND_ENV} is required for command-backed evaluation.")
        timeout = int(os.environ.get(AGENT_TIMEOUT_ENV) or 180)
        return cls(command=shlex.split(cmd), timeout_seconds=timeout)

    def run_role(self, role: str, prompt: str) -> dict[str, Any]:
        """Run one role through the external command; retry transient failures (stateless prompt→JSON)."""
        last_error: Exception | None = None
        for attempt in range(1, max(1, self.max_attempts) + 1):
            try:
                return self._attempt(prompt)
            except (RuntimeError, ValueError) as exc:
                last_error = exc
                self.retry_log.append({"role": role, "attempt": attempt, "reason": str(exc)})
                if attempt < self.max_attempts:
                    print(f"WARNING: {role} command failed on attempt {attempt}; retrying: {exc}", file=sys.stderr)
        raise RuntimeError(f"{role} command failed after {self.max_attempts} attempts: {last_error}") from last_error

    def _attempt(self, prompt: str) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                self.command, input=prompt, text=True, check=False,
                capture_output=True, timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"command timed out after {self.timeout_seconds}s") from exc
        if completed.returncode != 0:
            raise RuntimeError(f"command exited {completed.returncode}: {completed.stderr.strip()[-300:]}")
        return parse_json_object(completed.stdout)


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("role command returned empty output")
    try:
        loaded = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if match:
            loaded = json.loads(match.group(1))
        else:
            start, end = stripped.find("{"), stripped.rfind("}")
            if start == -1 or end <= start:
                raise
            loaded = json.loads(stripped[start:end + 1])
    if not isinstance(loaded, dict):
        raise ValueError("role command must return a JSON object")
    return loaded
