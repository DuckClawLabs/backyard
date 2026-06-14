"""MCP signal tools — signal_ready, wait_for_signal."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import Tool
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.server.auth import AuthContext
from backyard.server.context.briefing import record_activity
from backyard.server.signals.engine import await_signal, publish_signal

TOOL_NAMES = {"signal_ready", "wait_for_signal"}

TOOLS: list[Tool] = [
    Tool(
        name="signal_ready",
        description=(
            "Broadcast that a milestone or dependency is complete. "
            "Any agents waiting on this topic will unblock immediately."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Signal topic, e.g. 'user-api', 'auth-middleware'"},
                "payload": {"type": "object", "description": "Optional structured data (e.g. contract id)"},
                "message": {"type": "string", "description": "Human-readable status message"},
                "scope": {
                    "type": "string",
                    "enum": ["branch", "project"],
                    "description": "Signal scope: 'branch' (default, only unblocks waiters on the same git branch) or 'project' (unblocks all branches — use for infra milestones).",
                },
            },
            "required": ["topic"],
        },
    ),
    Tool(
        name="wait_for_signal",
        description=(
            "Block until the specified signal topic is published. "
            "Returns immediately if the signal was already published in this session."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Signal topic to wait for"},
                "timeout": {"type": "integer", "description": "Seconds before timing out (default: 300)"},
            },
            "required": ["topic"],
        },
    ),
]


async def dispatch(name: str, args: dict[str, Any], db: AsyncSession, auth: AuthContext) -> str:
    project_id = auth.project_id

    if name == "signal_ready":
        topic = args["topic"]
        payload = args.get("payload", {})
        message = args.get("message", "")

        signal = await publish_signal(
            db=db,
            project_id=project_id,
            topic=topic,
            engineer_id=auth.engineer_id,
            role=auth.role,
            git_branch=auth.git_branch,
            payload=payload,
            message=message,
            scope=args.get("scope", "branch"),
        )
        await record_activity(project_id, f"{auth.role} ({auth.engineer_name}): signaled '{topic}' ready")
        return f"Signal '{topic}' published (id: {signal.id})."

    if name == "wait_for_signal":
        topic = args["topic"]
        timeout = int(args.get("timeout", 300))

        result = await await_signal(db=db, project_id=project_id, topic=topic, git_branch=auth.git_branch, timeout=timeout)

        if result.timed_out:
            return json.dumps({"timed_out": True, "topic": topic})

        return json.dumps({
            "timed_out": False,
            "topic": topic,
            "signal_id": result.signal.id if result.signal else None,
            "published_by": result.signal.published_by_role if result.signal else None,
            "payload": result.signal.payload if result.signal else {},
            "message": result.signal.message if result.signal else "",
        }, indent=2)

    return f"Unknown tool: {name}"
