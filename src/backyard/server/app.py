"""FastAPI application entry point."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from mcp.server.sse import SseServerTransport

from backyard.server.auth import AuthContext, authenticate
from backyard.server.config import settings
from backyard.server.context.briefing import assemble_briefing
from backyard.server.conflicts.surface import get_open_cards, resolve_card
from backyard.server.db import AsyncSessionLocal, engine
from backyard.server.mcp_hub.server import build_mcp_server
from backyard.server.project_registry import (
    get_active_project,
    get_engineer_role_for_project,
    set_active_project,
)
from backyard.server.redis_client import close_redis, get_redis

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backyard MCP server starting")
    yield
    await close_redis()
    await engine.dispose()
    logger.info("Backyard MCP server stopped")


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


# ── Single MCP endpoint — one URL, all projects ───────────────────────────────

@app.get("/mcp")
async def mcp_sse(request: Request):
    """
    SSE endpoint for MCP connections.

    One URL per organization — engineers never change this after initial setup.
    Project is resolved from:
      1. X-Git-Remote header sent by Claude Code (git remote of the current repo)
      2. X-Project-Id header (explicit override)
      3. Previously set active project for this session (set_active_project tool)
      4. Falls back to "default" with a hint to call set_active_project

    Engineers configure once in .claude/settings.json:
      { "mcpServers": { "backyard": { "url": "https://backyard.yourcompany.com/mcp" } } }
    """
    auth = await authenticate(request)

    # Resolve project from request context
    project_id = await _resolve_project(request, auth)
    auth_role = await get_engineer_role_for_project(project_id, auth.engineer_id)

    # Register session in Redis
    redis = get_redis()
    await redis.hset(
        f"sessions:{project_id}",
        auth.engineer_id,
        json.dumps({
            "name": auth.engineer_name,
            "role": auth_role,
            "session_id": auth.session_id,
            "connected_since": datetime.now(timezone.utc).isoformat(),
        }),
    )
    await redis.publish(
        f"events:{project_id}",
        json.dumps({"type": "engineer_connected", "engineer_name": auth.engineer_name, "role": auth_role}),
    )

    logger.info("Engineer %s (%s) connected to project %s", auth.engineer_name, auth_role, project_id)

    try:
        mcp_server = build_mcp_server(
            auth=auth,
            project_id=project_id,
            role=auth_role,
            db_factory=AsyncSessionLocal,
        )
        transport = SseServerTransport("/mcp/messages")
        async with transport.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())
    finally:
        await redis.hdel(f"sessions:{project_id}", auth.engineer_id)
        await redis.publish(
            f"events:{project_id}",
            json.dumps({"type": "engineer_disconnected", "engineer_name": auth.engineer_name}),
        )
        logger.info("Engineer %s disconnected from project %s", auth.engineer_name, project_id)


@app.post("/mcp/messages")
async def mcp_messages(request: Request):
    return JSONResponse({"ok": True})


# ── Dashboard and project-scoped REST endpoints ───────────────────────────────

@app.get("/project/{project_id}", response_class=HTMLResponse)
async def dashboard(project_id: str):
    try:
        import importlib.resources
        html_path = importlib.resources.files("backyard.dashboard") / "index.html"
        return HTMLResponse(html_path.read_text())
    except Exception:
        return HTMLResponse(f"<h1>Backyard — {project_id}</h1>")


@app.get("/project/{project_id}/status")
async def project_status(project_id: str, request: Request):
    await authenticate(request)
    redis = get_redis()
    active_raw = await redis.hgetall(f"sessions:{project_id}")
    active = []
    for _eng_id, data_str in active_raw.items():
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


@app.get("/project/{project_id}/briefing")
async def get_briefing(project_id: str, request: Request):
    auth = await authenticate(request)
    role = await get_engineer_role_for_project(project_id, auth.engineer_id)
    async with AsyncSessionLocal() as db:
        briefing = await assemble_briefing(
            db=db,
            project_id=project_id,
            project_name=project_id,
            engineer_id=auth.engineer_id,
            role=role,
        )
    return {"briefing": briefing.render(), "data": briefing.model_dump(mode="json")}


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


@app.post("/project/{project_id}/members/{engineer_id}/role")
async def set_member_role(project_id: str, engineer_id: str, request: Request):
    await authenticate(request)
    body = await request.json()
    role = body.get("role", "backend")
    valid_roles = {"frontend", "backend", "devops", "reviewer"}
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose: {valid_roles}")
    redis = get_redis()
    await redis.hset(f"member_roles:{project_id}", engineer_id, role)
    return {"engineer_id": engineer_id, "project_id": project_id, "role": role}


# ── SSE events stream for the dashboard ──────────────────────────────────────

@app.get("/project/{project_id}/events")
async def project_events(project_id: str, request: Request):
    """Server-Sent Events stream for the dashboard's live updates."""
    await authenticate(request)
    from starlette.responses import StreamingResponse
    import asyncio

    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"events:{project_id}")

    async def event_stream():
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        finally:
            await pubsub.unsubscribe(f"events:{project_id}")
            await pubsub.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _resolve_project(request: Request, auth: AuthContext) -> str:
    """
    Resolve which project this session belongs to.
    Priority: explicit header > git remote header > session cache > default
    """
    # 1. Explicit project ID header (engineer or Claude Code can set this)
    explicit = request.headers.get("X-Project-Id")
    if explicit:
        await set_active_project(auth.session_id, explicit)
        return explicit

    # 2. Git remote header — Claude Code may send the current repo's remote
    git_remote = request.headers.get("X-Git-Remote")
    if git_remote:
        async with AsyncSessionLocal() as db:
            from backyard.server.project_registry import resolve_project_from_remote
            project = await resolve_project_from_remote(db, git_remote)
            if project:
                await set_active_project(auth.session_id, project.id)
                return project.id

    # 3. Previously set active project for this session
    cached = await get_active_project(auth.session_id)
    if cached:
        return cached

    # 4. Fallback — no project detected yet
    # Return a sentinel; the MCP Hub will prompt the engineer to call set_active_project
    return "unset"


def main() -> None:
    import uvicorn
    uvicorn.run("backyard.server.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
