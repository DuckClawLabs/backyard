"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.sse import SseServerTransport

from backyard.server.auth import AuthContext, authenticate
from backyard.server.config import settings
from backyard.server.context.briefing import (
    assemble_briefing,
    get_active_sessions,
    get_open_decisions,
)
from backyard.server.conflicts.surface import get_open_cards, resolve_card
from backyard.server.db import AsyncSessionLocal, engine
from backyard.server.mcp_hub.server import build_mcp_server
from backyard.server.redis_client import close_redis, get_redis

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backyard MCP server starting up")
    yield
    await close_redis()
    await engine.dispose()
    logger.info("Backyard MCP server shut down")


app = FastAPI(
    title="Backyard MCP Coordination Server",
    description="Shared brain for engineering teams using Claude Code.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# ── MCP endpoint (SSE) ────────────────────────────────────────────────────────

@app.get("/project/{project_id}/mcp")
async def mcp_sse(project_id: str, request: Request):
    """
    SSE endpoint for MCP connections. Claude Code connects here.
    Each connection gets its own MCP server instance with its role's tool set.
    """
    auth = await authenticate(request)
    auth.role = await _get_engineer_role(project_id, auth.engineer_id)

    # Register session in Redis
    redis = get_redis()
    await redis.hset(
        f"sessions:{project_id}",
        auth.engineer_id,
        json.dumps({
            "name": auth.engineer_name,
            "role": auth.role,
            "session_id": auth.session_id,
            "connected_since": datetime.now(timezone.utc).isoformat(),
        }),
    )
    await redis.publish(
        f"events:{project_id}",
        json.dumps({
            "type": "engineer_connected",
            "engineer_name": auth.engineer_name,
            "role": auth.role,
        }),
    )

    logger.info("Engineer %s (%s) connected to project %s", auth.engineer_name, auth.role, project_id)

    try:
        mcp_server = build_mcp_server(auth, AsyncSessionLocal)
        transport = SseServerTransport(f"/project/{project_id}/mcp/messages")
        async with transport.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())
    finally:
        await redis.hdel(f"sessions:{project_id}", auth.engineer_id)
        await redis.publish(
            f"events:{project_id}",
            json.dumps({"type": "engineer_disconnected", "engineer_name": auth.engineer_name}),
        )
        logger.info("Engineer %s disconnected from project %s", auth.engineer_name, project_id)


@app.post("/project/{project_id}/mcp/messages")
async def mcp_messages(project_id: str, request: Request):
    """POST endpoint for MCP message passing (used by the SSE transport)."""
    # Handled internally by SseServerTransport; this route just needs to exist.
    return JSONResponse({"ok": True})


# ── Briefing endpoint (for testing / dashboard) ───────────────────────────────

@app.get("/project/{project_id}/briefing")
async def get_briefing(project_id: str, request: Request):
    auth = await authenticate(request)
    async with AsyncSessionLocal() as db:
        briefing = await assemble_briefing(
            db=db,
            project_id=project_id,
            project_name=project_id,  # use project_id as name in Phase 1A
            engineer_id=auth.engineer_id,
            role=auth.role,
        )
    return {"briefing": briefing.render(), "data": briefing.model_dump(mode="json")}


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@app.get("/project/{project_id}/status")
async def project_status(project_id: str, request: Request):
    await authenticate(request)
    redis = get_redis()
    active_raw = await redis.hgetall(f"sessions:{project_id}")
    active = []
    for eng_id, data_str in active_raw.items():
        try:
            active.append(json.loads(data_str))
        except json.JSONDecodeError:
            pass

    async with AsyncSessionLocal() as db:
        open_cards = await get_open_cards(db, project_id)

    return {
        "project_id": project_id,
        "active_sessions": active,
        "open_resolutions": [c.model_dump(mode="json") for c in open_cards],
    }


@app.post("/project/{project_id}/resolutions/{resolution_id}/resolve")
async def resolve_resolution(project_id: str, resolution_id: str, request: Request):
    auth = await authenticate(request)
    body = await request.json()

    async with AsyncSessionLocal() as db:
        decision = await resolve_card(
            db=db,
            project_id=project_id,
            resolution_id=resolution_id,
            decision=body["decision"],
            decided_by=[auth.engineer_id],
            record_as_adr=body.get("record_as_adr", False),
            adr_title=body.get("adr_title", ""),
            adr_affects=body.get("adr_affects", []),
        )

    return decision.model_dump(mode="json")


# ── Dashboard SPA ─────────────────────────────────────────────────────────────

@app.get("/project/{project_id}", response_class=HTMLResponse)
async def dashboard(project_id: str):
    import importlib.resources
    try:
        html_path = importlib.resources.files("backyard.dashboard") / "index.html"
        return HTMLResponse(html_path.read_text())
    except Exception:
        return HTMLResponse(f"<h1>Backyard</h1><p>Project: {project_id}</p>")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_engineer_role(project_id: str, engineer_id: str) -> str:
    """
    Look up an engineer's role for this project.
    In Phase 1A this falls back to 'backend'; Phase 1B adds proper DB lookup.
    """
    redis = get_redis()
    role = await redis.hget(f"member_roles:{project_id}", engineer_id)
    return role or "backend"


@app.post("/project/{project_id}/members/{engineer_id}/role")
async def set_role(project_id: str, engineer_id: str, request: Request):
    """Allow an engineer to set their role for a project."""
    auth = await authenticate(request)
    body = await request.json()
    role = body.get("role", "backend")

    valid_roles = {"frontend", "backend", "devops", "reviewer"}
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {valid_roles}")

    redis = get_redis()
    await redis.hset(f"member_roles:{project_id}", engineer_id, role)
    return {"engineer_id": engineer_id, "project_id": project_id, "role": role}


def main() -> None:
    import uvicorn
    uvicorn.run("backyard.server.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
