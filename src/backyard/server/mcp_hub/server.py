"""MCP Hub — one MCP server instance per engineer session."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from mcp.server import Server
from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.server.auth import AuthContext
from backyard.server.roles.definitions import has_capability
from backyard.server.mcp_hub import context_tools, signal_tools, coord_tools, file_tools
from backyard.server.audit import log as audit_log


def build_mcp_server(
    auth: AuthContext,
    project_id: str,
    role: str,
    db_factory: Callable[[], AsyncSession],
) -> Server:
    """Build and return a configured MCP Server for this engineer's session.

    Tool calls are intercepted here for:
      - capability check (role enforcement)
      - audit logging
      - domain check on write_file (triggers proposal flow)
    """
    auth.project_id = project_id
    auth.role = role
    server = Server(name="backyard", version="0.1.0")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        all_tools = [
            *context_tools.TOOLS,
            *signal_tools.TOOLS,
            *coord_tools.TOOLS,
            *file_tools.TOOLS,
        ]
        return [t for t in all_tools if has_capability(auth.role, t.name)]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if not has_capability(auth.role, name):
            return [TextContent(type="text", text=f"Error: role '{auth.role}' cannot use tool '{name}'.")]

        start = time.monotonic()
        result_text = ""

        async with db_factory() as db:
            try:
                if name in context_tools.TOOL_NAMES:
                    result_text = await context_tools.dispatch(name, arguments, db, auth)
                elif name in signal_tools.TOOL_NAMES:
                    result_text = await signal_tools.dispatch(name, arguments, db, auth)
                elif name in coord_tools.TOOL_NAMES:
                    result_text = await coord_tools.dispatch(name, arguments, db, auth)
                elif name in file_tools.TOOL_NAMES:
                    result_text = await file_tools.dispatch(name, arguments, db, auth)
                else:
                    result_text = f"Unknown tool: {name}"
            except Exception as exc:
                result_text = f"Error: {exc}"

            latency = int((time.monotonic() - start) * 1000)
            await audit_log.append(
                db=db,
                project_id=auth.project_id,
                engineer_id=auth.engineer_id,
                role=auth.role,
                session_id=auth.session_id,
                git_branch=auth.git_branch,
                tool_name=name,
                arguments=arguments,
                result_summary=result_text[:200],
                latency_ms=latency,
            )

        return [TextContent(type="text", text=result_text)]

    return server
