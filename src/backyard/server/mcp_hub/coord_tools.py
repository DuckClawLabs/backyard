"""MCP coordination tools — raise_resolution, propose_cross_domain_edit, request_clarification."""

from __future__ import annotations

import json
import uuid
from typing import Any

from mcp.types import Tool
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.server.auth import AuthContext
from backyard.server.conflicts.surface import create_resolution_card
from backyard.server.redis_client import get_redis

TOOL_NAMES = {"raise_resolution", "propose_cross_domain_edit", "request_clarification"}

TOOLS: list[Tool] = [
    Tool(
        name="raise_resolution",
        description=(
            "Surface a conflict or contradictory instruction to all engineers on this project. "
            "This pauses the current action until engineers resolve the conflict on the dashboard."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short description of the conflict"},
                "conflict_a": {"type": "string", "description": "One side of the conflict"},
                "conflict_b": {"type": "string", "description": "The other side"},
                "affects": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File paths or domain names affected",
                },
                "agent_read": {"type": "string", "description": "The agent's read of the trade-off (optional)"},
            },
            "required": ["title", "conflict_a", "conflict_b"],
        },
    ),
    Tool(
        name="propose_cross_domain_edit",
        description=(
            "Request permission to edit a file outside your role's domain. "
            "Posts a request to the owning engineer on the dashboard."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file you want to edit"},
                "reason": {"type": "string", "description": "Why you need to edit it"},
                "intent": {"type": "string", "description": "Brief description of the planned change"},
            },
            "required": ["path", "reason", "intent"],
        },
    ),
    Tool(
        name="request_clarification",
        description="Post a question to a specific role's engineer, visible on the dashboard.",
        inputSchema={
            "type": "object",
            "properties": {
                "to_role": {"type": "string", "description": "The role to ask (e.g. 'backend', 'devops')"},
                "question": {"type": "string", "description": "The question"},
                "context": {"type": "string", "description": "Relevant context (optional)"},
            },
            "required": ["to_role", "question"],
        },
    ),
]


async def dispatch(name: str, args: dict[str, Any], db: AsyncSession, auth: AuthContext) -> str:
    project_id = auth.role  # TODO: real project_id
    redis = get_redis()

    if name == "raise_resolution":
        card = await create_resolution_card(
            db=db,
            project_id=project_id,
            title=args["title"],
            conflict_a=args["conflict_a"],
            conflict_b=args["conflict_b"],
            affects=args.get("affects", []),
            raised_by=auth.engineer_id,
            raised_by_role=auth.role,
            agent_read=args.get("agent_read", ""),
        )
        return (
            f"Conflict surfaced to engineers (id: {card.id}).\n"
            "The engineers will see a resolution card on the dashboard. "
            "Do not proceed with the affected action until the conflict is resolved."
        )

    if name == "propose_cross_domain_edit":
        proposal_id = str(uuid.uuid4())
        await redis.hset(
            f"proposal:{project_id}:{proposal_id}",
            mapping={
                "path": args["path"],
                "reason": args["reason"],
                "intent": args["intent"],
                "requested_by": auth.engineer_id,
                "requested_by_role": auth.role,
                "status": "pending",
            },
        )
        await redis.publish(
            f"events:{project_id}",
            json.dumps({
                "type": "cross_domain_proposal",
                "proposal_id": proposal_id,
                "path": args["path"],
                "requested_by_role": auth.role,
                "intent": args["intent"],
            }),
        )
        return (
            f"Cross-domain edit proposed (id: {proposal_id}).\n"
            f"Waiting for the owning engineer to approve access to '{args['path']}'."
        )

    if name == "request_clarification":
        clarification_id = str(uuid.uuid4())
        await redis.publish(
            f"events:{project_id}",
            json.dumps({
                "type": "clarification_request",
                "clarification_id": clarification_id,
                "to_role": args["to_role"],
                "from_role": auth.role,
                "from_engineer": auth.engineer_name,
                "question": args["question"],
                "context": args.get("context", ""),
            }),
        )
        return (
            f"Clarification requested from {args['to_role']} (id: {clarification_id}).\n"
            "The engineer will see your question on the dashboard. "
            "Their reply will arrive as a signal."
        )

    return f"Unknown tool: {name}"
