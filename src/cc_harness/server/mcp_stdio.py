"""Minimal MCP-style stdio server (JSON-RPC 2.0, line-delimited).

Forked/minimized from `up_harness/server/mcp_stdio.py`. M1 exposes `workflow.list` and `workflow.start`
so the skeleton is drivable end-to-end (plan §7 M1). More tools (status, outputs, export, feedback,
rerun) arrive with later milestones.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from cc_harness.engine.runner import WorkflowRunner
from cc_harness.engine.workflow import list_workflows

SERVER_INFO = {"name": "cc-harness", "version": "0.0.1"}

TOOLS = [
    {
        "name": "workflow.list",
        "description": "List available workflows.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "workflow.start",
        "description": "Start a workflow run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workflow_name": {"type": "string"},
                "inputs": {"type": "object"},
            },
            "required": ["workflow_name"],
        },
    },
]


def _text_result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "workflow.list":
        return _text_result({"workflows": list_workflows()})
    if name == "workflow.start":
        workflow_name = arguments.get("workflow_name")
        if not workflow_name:
            raise ValueError("workflow.start requires 'workflow_name'.")
        run = WorkflowRunner().start(str(workflow_name), arguments.get("inputs") or {})
        return _text_result(
            {
                "run_id": run.run_id,
                "workflow_name": run.workflow_name,
                "status": run.status,
                "phases": {pid: p.status for pid, p in run.phases.items()},
            }
        )
    raise ValueError(f"Unknown tool: {name}")


def handle(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    req_id = request.get("id")
    if method == "initialize":
        result: Any = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = request.get("params") or {}
        try:
            result = _call_tool(str(params.get("name")), params.get("arguments") or {})
        except Exception as exc:  # noqa: BLE001 - report as JSON-RPC error
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}}
    elif method is not None and method.startswith("notifications/"):
        return None  # notifications get no response
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
