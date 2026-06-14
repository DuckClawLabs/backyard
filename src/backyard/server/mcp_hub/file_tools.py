"""MCP file tools — read_file, write_file, list_files (with domain check and summary generation)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.types import Tool
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.server.auth import AuthContext
from backyard.server.context.briefing import record_activity
from backyard.server.context.store import upsert_file_summary
from backyard.server.context.summarizer import summarize_file
from backyard.server.roles.definitions import needs_proposal

TOOL_NAMES = {"read_file", "write_file", "list_files"}

TOOLS: list[Tool] = [
    Tool(
        name="read_file",
        description="Read a file from the project.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="write_file",
        description="Write content to a file. Triggers file summary generation and domain check.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to project root"},
                "content": {"type": "string", "description": "File content"},
            },
            "required": ["path", "content"],
        },
    ),
    Tool(
        name="list_files",
        description="List files in a directory.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path (default: project root)"},
                "pattern": {"type": "string", "description": "Glob pattern filter (optional)"},
            },
        },
    ),
]


def _safe_path(path: str) -> Path:
    """Resolve path and ensure it doesn't escape the working directory."""
    resolved = Path(os.getcwd()).resolve() / path
    resolved = resolved.resolve()
    if not str(resolved).startswith(str(Path(os.getcwd()).resolve())):
        raise PermissionError(f"Path traversal blocked: {path!r}")
    return resolved


async def dispatch(name: str, args: dict[str, Any], db: AsyncSession, auth: AuthContext) -> str:
    project_id = auth.project_id

    if name == "read_file":
        path = args["path"]
        try:
            safe = _safe_path(path)
            return safe.read_text(encoding="utf-8")
        except FileNotFoundError:
            return f"File not found: {path}"
        except PermissionError as e:
            return f"Error: {e}"

    if name == "write_file":
        path = args["path"]
        content = args["content"]

        # Domain check — redirect to proposal flow if out-of-domain
        if needs_proposal(auth.role, path):
            from backyard.server.mcp_hub.coord_tools import dispatch as coord_dispatch
            return await coord_dispatch(
                "propose_cross_domain_edit",
                {
                    "path": path,
                    "reason": "write_file called on out-of-domain path",
                    "intent": f"Write {len(content)} characters to {path}",
                },
                db,
                auth,
            )

        try:
            safe = _safe_path(path)
            safe.parent.mkdir(parents=True, exist_ok=True)
            safe.write_text(content, encoding="utf-8")
        except PermissionError as e:
            return f"Error: {e}"

        # Generate file summary asynchronously (best effort)
        try:
            summary_text, exports = await summarize_file(path, content)
            await upsert_file_summary(
                db,
                project_id=project_id,
                path=path,
                summary=summary_text,
                exports=exports,
                engineer_id=auth.engineer_id,
                git_branch=auth.git_branch,
            )
        except Exception:
            pass  # summary failure must never block the write

        await record_activity(
            project_id, f"{auth.role} ({auth.engineer_name}): wrote {path}"
        )
        return f"Wrote {len(content)} characters to {path}."

    if name == "list_files":
        base = args.get("path", ".")
        pattern = args.get("pattern", "*")
        try:
            safe = _safe_path(base)
            files = [str(p.relative_to(safe)) for p in safe.rglob(pattern) if p.is_file()]
            return "\n".join(files[:200]) if files else "No files found."
        except (FileNotFoundError, PermissionError) as e:
            return f"Error: {e}"

    return f"Unknown tool: {name}"
