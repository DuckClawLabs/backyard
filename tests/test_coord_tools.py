"""Tests for MCP coordination tools: set_active_project, raise_resolution, propose_cross_domain_edit, request_clarification."""

from __future__ import annotations

import json

import pytest

from backyard.server.mcp_hub import coord_tools


PROJECT = "proj-coord"


@pytest.fixture
def auth(alice):
    alice.project_id = PROJECT
    return alice


# ── set_active_project ────────────────────────────────────────────────────────

async def test_set_active_project(db, auth, fake_redis):
    result = await coord_tools.dispatch(
        "set_active_project", {"project_id": "my-project"}, db, auth
    )
    assert "my-project" in result

    stored = await fake_redis.get(f"active_project:{auth.session_id}")
    assert stored == "my-project"


# ── raise_resolution ──────────────────────────────────────────────────────────

async def test_raise_resolution_returns_id(db, auth, fake_redis):
    result = await coord_tools.dispatch(
        "raise_resolution",
        {
            "title": "API design conflict",
            "conflict_a": "Use REST",
            "conflict_b": "Use GraphQL",
            "affects": ["api/**"],
            "agent_read": "Both have merit; REST is simpler for MVP.",
        },
        db,
        auth,
    )
    assert "Conflict surfaced" in result
    assert "id:" in result


async def test_raise_resolution_stores_in_redis(db, auth, fake_redis):
    await coord_tools.dispatch(
        "raise_resolution",
        {"title": "DB choice", "conflict_a": "Postgres", "conflict_b": "MySQL"},
        db,
        auth,
    )
    members = await fake_redis.smembers(f"open_resolutions:{PROJECT}")
    assert len(members) == 1


async def test_raise_resolution_stores_card_title(db, auth, fake_redis):
    await coord_tools.dispatch(
        "raise_resolution",
        {"title": "Cache strategy", "conflict_a": "Redis", "conflict_b": "Memcached"},
        db,
        auth,
    )
    members = await fake_redis.smembers(f"open_resolutions:{PROJECT}")
    assert len(members) == 1
    card_id = next(iter(members))
    card = await fake_redis.hgetall(f"resolution:{PROJECT}:{card_id}")
    assert card["title"] == "Cache strategy"


# ── propose_cross_domain_edit ─────────────────────────────────────────────────

async def test_propose_cross_domain_edit_returns_id(db, auth, fake_redis):
    result = await coord_tools.dispatch(
        "propose_cross_domain_edit",
        {
            "path": "ui/App.tsx",
            "reason": "Need to fix routing bug that spans backend and frontend",
            "intent": "Update App.tsx router config",
        },
        db,
        auth,
    )
    assert "proposed" in result.lower()
    assert "ui/App.tsx" in result


async def test_propose_cross_domain_edit_stores_in_redis(db, auth, fake_redis):
    await coord_tools.dispatch(
        "propose_cross_domain_edit",
        {"path": "infra/nginx.conf", "reason": "Need DNS change", "intent": "Add upstream"},
        db,
        auth,
    )
    # A proposal hash should exist
    keys = []
    async for key in fake_redis.scan_iter(f"proposal:{PROJECT}:*"):
        keys.append(key)
    assert len(keys) == 1

    proposal = await fake_redis.hgetall(keys[0])
    assert proposal["path"] == "infra/nginx.conf"
    assert proposal["status"] == "pending"


async def test_propose_cross_domain_edit_stores_intent(db, auth, fake_redis):
    await coord_tools.dispatch(
        "propose_cross_domain_edit",
        {"path": "styles/global.css", "reason": "branding update", "intent": "Change colors"},
        db,
        auth,
    )
    keys = [k async for k in fake_redis.scan_iter(f"proposal:{PROJECT}:*")]
    assert len(keys) >= 1
    proposal = await fake_redis.hgetall(keys[-1])
    assert proposal["intent"] == "Change colors"
    assert proposal["path"] == "styles/global.css"


# ── request_clarification ─────────────────────────────────────────────────────

async def test_request_clarification_returns_id(db, auth, fake_redis):
    result = await coord_tools.dispatch(
        "request_clarification",
        {
            "to_role": "devops",
            "question": "What is the Redis cluster config in prod?",
            "context": "Setting up connection pooling",
        },
        db,
        auth,
    )
    assert "devops" in result
    assert "id:" in result


async def test_request_clarification_to_role_in_reply(db, auth, fake_redis):
    result = await coord_tools.dispatch(
        "request_clarification",
        {"to_role": "frontend", "question": "Which component handles auth?"},
        db,
        auth,
    )
    assert "frontend" in result
    assert "id:" in result


async def test_unknown_tool(db, auth, fake_redis):
    result = await coord_tools.dispatch("nonexistent_tool", {}, db, auth)
    assert "Unknown tool" in result
