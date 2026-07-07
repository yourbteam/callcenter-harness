#!/usr/bin/env python3
"""M1 smoke: prove the cc_harness skeleton boots and runs the no-op workflow.

Checks (1) the runner completes the noop workflow in-process, and (2) the MCP stdio server answers
initialize / tools/list / workflow.list / workflow.start as a subprocess. Run:

    PYTHONPATH=src python3 scripts/cc_smoke.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from cc_harness.engine.runner import WorkflowRunner  # noqa: E402
from cc_harness.engine.workflow import list_workflows  # noqa: E402


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        raise SystemExit(1)


def main() -> None:
    # 1. In-process runner
    check("noop workflow is discoverable", "noop" in list_workflows(), f"found {list_workflows()}")
    run = WorkflowRunner().start("noop")
    check("noop run completed", run.status == "completed", f"status={run.status}")
    check("noop phase completed", run.phases["noop-1"].status == "completed")

    # 2. MCP stdio server as a subprocess
    reqs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "workflow.list", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "workflow.start", "arguments": {"workflow_name": "noop"}}},
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "cc_harness.server.mcp_stdio"],
        input="\n".join(json.dumps(r) for r in reqs) + "\n",
        capture_output=True, text=True, cwd=REPO,
        env={"PYTHONPATH": str(REPO / "src"), "PATH": __import__("os").environ.get("PATH", "")},
    )
    lines = [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]
    by_id = {r.get("id"): r for r in lines}
    check("stdio initialize ok", by_id.get(1, {}).get("result", {}).get("serverInfo", {}).get("name") == "cc-harness")
    check("stdio tools/list has workflow.start",
          any(t["name"] == "workflow.start" for t in by_id.get(2, {}).get("result", {}).get("tools", [])))
    wf_list_text = json.loads(by_id.get(3, {}).get("result", {}).get("content", [{}])[0].get("text", "{}"))
    check("stdio workflow.list returns noop", "noop" in wf_list_text.get("workflows", []))
    start_text = json.loads(by_id.get(4, {}).get("result", {}).get("content", [{}])[0].get("text", "{}"))
    check("stdio workflow.start completed", start_text.get("status") == "completed", f"payload={start_text}")

    print("\nM1 smoke: ALL PASS")


if __name__ == "__main__":
    main()
