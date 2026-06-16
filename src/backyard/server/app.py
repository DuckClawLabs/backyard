"""FastAPI application entry point."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from mcp.server.sse import SseServerTransport

from backyard.db.models import Org, Project as ProjectModel
from backyard.server.auth import AuthContext, authenticate
from backyard.server.config import settings
from backyard.server.context.briefing import assemble_briefing
from backyard.server.conflicts.surface import get_open_cards, resolve_card
from backyard.server.db import AsyncSessionLocal, engine
from backyard.server.mcp_hub.server import build_mcp_server
from backyard.server.profile_reader import ProfileInvalidError, ProfileNotFoundError, load_profile
from backyard.server.project_registry import (
    get_active_project,
    get_engineer_role_for_project,
    set_active_project,
)
from backyard.server.redis_client import close_redis, get_redis

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

# Singleton SSE transport — must be shared between GET /mcp and POST /mcp/messages
# so that handle_post_message can route to the correct in-flight SSE session.
_sse_transport = SseServerTransport("/mcp/messages")


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

    Engineers configure once in .claude/settings.json:
      { "mcpServers": { "backyard": { "url": "https://backyard.yourcompany.com/mcp" } } }

    Identity and project are resolved from .backyard-mcp/me.yaml in the workspace root.
    The workspace root is sent by Claude Code via the X-Workspace-Root header.
    """
    auth = await authenticate(request)

    # Load identity + project from the engineer's me.yaml
    workspace_root = request.headers.get("X-Workspace-Root", ".")
    try:
        profile = load_profile(workspace_root)
    except ProfileNotFoundError as e:
        # Return a helpful MCP error so the engineer sees it in their Claude session
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(str(e), status_code=200)  # 200 so Claude Code shows the message
    except ProfileInvalidError as e:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(f"Invalid me.yaml: {e}", status_code=200)

    project_id = _slug_to_uuid(profile.id)
    org_id = _slug_to_uuid("default-org")
    auth.engineer_name = profile.engineer.name
    auth.engineer_id = _email_to_id(profile.engineer.email)
    auth_role = profile.engineer.role
    auth.git_branch = _read_git_branch(workspace_root)

    # Ensure org + project rows exist so FK constraints on all tables pass
    await _ensure_project(project_id, profile.name, org_id)

    # If the profile defines custom owns, store them for role enforcement
    if profile.engineer.owns:
        redis = get_redis()
        await redis.set(
            f"custom_owns:{project_id}:{auth.engineer_id}",
            ",".join(profile.engineer.owns),
            ex=86400,
        )

    # Register session in Redis — keyed by session_id so multiple sessions
    # from the same engineer (e.g. different branches) coexist independently.
    redis = get_redis()
    await redis.hset(
        f"sessions:{project_id}",
        auth.session_id,
        json.dumps({
            "name": auth.engineer_name,
            "engineer_id": auth.engineer_id,
            "role": auth_role,
            "git_branch": auth.git_branch,
            "session_id": auth.session_id,
            "connected_since": datetime.now(timezone.utc).isoformat(),
        }),
    )
    await redis.publish(
        f"events:{project_id}",
        json.dumps({
            "type": "engineer_connected",
            "engineer_name": auth.engineer_name,
            "role": auth_role,
            "git_branch": auth.git_branch,
        }),
    )

    logger.info(
        "Engineer %s (%s, branch: %s) connected to project %s",
        auth.engineer_name, auth_role, auth.git_branch, project_id,
    )

    try:
        mcp_server = build_mcp_server(
            auth=auth,
            project_id=project_id,
            role=auth_role,
            db_factory=AsyncSessionLocal,
        )
        async with _sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())
    finally:
        await redis.hdel(f"sessions:{project_id}", auth.session_id)
        await redis.publish(
            f"events:{project_id}",
            json.dumps({"type": "engineer_disconnected", "engineer_name": auth.engineer_name, "git_branch": auth.git_branch}),
        )
        logger.info("Engineer %s (branch: %s) disconnected from project %s", auth.engineer_name, auth.git_branch, project_id)


@app.post("/mcp/messages")
async def mcp_messages(request: Request):
    from fastapi.responses import JSONResponse
    session_id = request.query_params.get("session_id", "")
    if session_id and session_id not in {str(k).replace("-", "") for k in _sse_transport._read_stream_writers}:
        # Session doesn't exist — server was likely restarted. Tell the client to reconnect.
        return JSONResponse(
            status_code=410,
            content={"error": "Session expired. Reconnect to /mcp to get a new session."},
        )
    await _sse_transport.handle_post_message(request.scope, request.receive, request._send)


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
    project_id = _slug_to_uuid(project_id)
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


@app.get("/project/{project_id}/file-summary")
async def get_file_summary_endpoint(project_id: str, path: str, request: Request):
    """REST fallback for get_file_summary — works without an active MCP session."""
    await authenticate(request)
    project_id = _slug_to_uuid(project_id)
    from backyard.server.context import store
    async with AsyncSessionLocal() as db:
        summary = await store.get_file_summary(db, project_id=project_id, path=path)
    if not summary:
        return {"path": path, "summary": None,
                "message": f"No summary available for '{path}'. Write the file through Backyard first."}
    return {
        "path": summary.path,
        "summary": summary.summary,
        "exports": summary.exports,
        "last_modified_by": summary.last_modified_by,
        "last_modified_at": summary.last_modified_at.isoformat(),
    }


@app.get("/project/{project_id}/briefing")
async def get_briefing(project_id: str, request: Request):
    auth = await authenticate(request)
    project_id = _slug_to_uuid(project_id)
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
    project_id = _slug_to_uuid(project_id)
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
    project_id = _slug_to_uuid(project_id)
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
    project_id = _slug_to_uuid(project_id)
    from starlette.responses import StreamingResponse
    import asyncio

    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"events:{project_id}")

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        finally:
            await pubsub.unsubscribe(f"events:{project_id}")
            await pubsub.aclose()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _email_to_id(email: str) -> str:
    """Derive a stable engineer ID from their email address."""
    import hashlib, uuid
    return str(uuid.UUID(hashlib.md5(email.lower().encode()).hexdigest()))


def _slug_to_uuid(slug: str) -> str:
    """Derive a stable project UUID from a human-readable slug (e.g. 'backyard')."""
    import hashlib, uuid
    return str(uuid.UUID(hashlib.md5(slug.lower().encode()).hexdigest()))


async def _ensure_project(project_id: str, project_name: str, org_id: str) -> None:
    """Upsert org + project rows so FK constraints on signals/contracts/adrs/etc pass."""
    from sqlalchemy import select as _sel

    async with AsyncSessionLocal() as db:
        if not (await db.execute(_sel(Org.id).where(Org.id == org_id))).scalar_one_or_none():
            try:
                db.add(Org(id=org_id, name="default"))
                await db.commit()
            except Exception:
                await db.rollback()

    async with AsyncSessionLocal() as db:
        if not (await db.execute(_sel(ProjectModel.id).where(ProjectModel.id == project_id))).scalar_one_or_none():
            try:
                db.add(ProjectModel(id=project_id, org_id=org_id, name=project_name))
                await db.commit()
            except Exception:
                await db.rollback()


def _read_git_branch(workspace_root: str) -> str:
    """Read the current git branch from the workspace's .git/HEAD file."""
    try:
        head = (Path(workspace_root) / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref: refs/heads/"):
            return head[len("ref: refs/heads/"):]
        return "detached"   # detached HEAD state
    except Exception:
        return "unknown"    # not a git repo or .git/HEAD unreadable


def main() -> None:
    import uvicorn
    uvicorn.run("backyard.server.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
