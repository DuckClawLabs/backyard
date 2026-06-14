"""MCP context tools — query_shared_context, publish_context, get_file_summary, get_project_status."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import Tool
from mcp.types import TextContent
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.server.auth import AuthContext
from backyard.server.context import store


TOOL_NAMES = {
    "query_shared_context",
    "publish_context",
    "get_file_summary",
    "get_project_status",
}

TOOLS: list[Tool] = [
    Tool(
        name="query_shared_context",
        description="Search the shared context store for contracts, ADRs, and file summaries.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or filter"},
                "type": {
                    "type": "string",
                    "enum": ["contract", "adr", "file_summary"],
                    "description": "Filter by artifact type (optional)",
                },
                "role": {"type": "string", "description": "Filter by publishing role (optional)"},
                "path_prefix": {"type": "string", "description": "Filter file summaries by path prefix (optional)"},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="publish_context",
        description="Publish a contract or ADR to the shared context store.",
        inputSchema={
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["contract", "adr"]},
                "id": {"type": "string", "description": "Unique ID, e.g. 'user-api-v1' or 'adr-database-choice'"},
                "content": {"type": "object", "description": "Artifact content (endpoints, types, decision, etc.)"},
                "description": {"type": "string", "description": "One-line human-readable summary"},
            },
            "required": ["type", "id", "content"],
        },
    ),
    Tool(
        name="get_file_summary",
        description="Get the auto-generated summary of any file in the project.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="get_project_status",
        description="Get the current state of the project — active engineers, contracts, open decisions.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


async def dispatch(name: str, args: dict[str, Any], db: AsyncSession, auth: AuthContext) -> str:
    project_id = auth.project_id

    if name == "query_shared_context":
        results = await store.search_context(
            db,
            project_id=project_id,
            artifact_type=args.get("type"),
            role=args.get("role"),
            path_prefix=args.get("path_prefix"),
        )
        if not results:
            return "No matching context found."
        return json.dumps(results, indent=2, default=str)

    if name == "publish_context":
        artifact_type = args["type"]
        artifact_id = args["id"]
        content = args["content"]
        description = args.get("description", "")

        if artifact_type == "contract":
            contract = await store.publish_contract(
                db,
                project_id=project_id,
                contract_id=artifact_id,
                published_by=auth.engineer_id,
                role=auth.role,
                content=content,
                description=description,
            )
            return f"Contract '{artifact_id}' published (v{contract.version})."

        if artifact_type == "adr":
            adr = await store.publish_adr(
                db,
                project_id=project_id,
                title=description or artifact_id,
                decision=content.get("decision", ""),
                affects=content.get("affects", []),
                decided_by=[auth.engineer_id],
                rationale=content.get("rationale", ""),
            )
            return f"ADR recorded: {adr.adr_ref} — {adr.title}"

        return f"Unknown artifact type: {artifact_type}"

    if name == "get_file_summary":
        path = args["path"]
        summary = await store.get_file_summary(db, project_id=project_id, path=path)
        if not summary:
            return f"No summary available for '{path}'. The file may not have been written through Backyard yet."
        return json.dumps({
            "path": summary.path,
            "summary": summary.summary,
            "exports": summary.exports,
            "last_modified_by": summary.last_modified_by,
            "last_modified_at": summary.last_modified_at.isoformat(),
        }, indent=2)

    if name == "get_project_status":
        from backyard.server.context.briefing import get_active_sessions, get_open_decisions, get_recent_activity
        active = await get_active_sessions(project_id)
        activity = await get_recent_activity(project_id)
        decisions = await get_open_decisions(project_id)
        contracts = await store.get_contracts(db, project_id)
        return json.dumps({
            "active_sessions": [{"engineer": s.engineer_name, "role": s.role} for s in active],
            "recent_activity": activity,
            "contracts": [{"id": c.id, "description": c.description} for c in contracts],
            "open_decisions": len(decisions),
        }, indent=2, default=str)

    return f"Unknown tool: {name}"
