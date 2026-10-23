#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal MCP client for McDonald's China MCP Server (Streamable HTTP).

Only depends on the standard library. The token is NEVER hardcoded: it is read
from the MCD_MCP_TOKEN environment variable.

Usage:
    from mcp_client import call_tool
    raw = call_tool("list-nutrition-foods")
"""

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"


class McpError(RuntimeError):
    pass


def _post(url, token, payload, session_id=None, timeout=30):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": "Bearer {}".format(token),
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return resp.headers.get("Mcp-Session-Id") or session_id, body


def _extract(body):
    """Return the JSON-RPC result, tolerating plain JSON and SSE frames."""
    body = body.strip()
    if body.startswith("{"):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            pass
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
    raise McpError("Cannot parse MCP response: {}".format(body[:200]))


def call_tool(tool_name, arguments=None, token=None, url=None, timeout=30):
    """Call one MCP tool and return its `result` object."""
    token = token or os.environ.get("MCD_MCP_TOKEN")
    if not token:
        raise McpError(
            "Missing MCD_MCP_TOKEN. Export it first:\n"
            "  export MCD_MCP_TOKEN='<your token from https://open.mcd.cn/mcp>'"
        )
    url = url or os.environ.get("MCD_MCP_URL", DEFAULT_URL)

    session_id, body = _post(
        url,
        token,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcd-calorie-buddy", "version": "1.0.0"},
            },
        },
        timeout=timeout,
    )
    _extract(body)

    session_id, body = _post(
        url,
        token,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
        },
        session_id=session_id,
        timeout=timeout,
    )
    msg = _extract(body)
    if "error" in msg:
        raise McpError("MCP error {}: {}".format(msg["error"].get("code"), msg["error"].get("message")))
    result = msg.get("result", {})
    if result.get("isError"):
        raise McpError("Tool reported an error: {}".format(result))
    return result


def tool_text(result):
    """Flatten a MCP tool result into plain text."""
    parts = []
    for block in result.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "list-nutrition-foods"
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(tool_text(call_tool(name, args)))
