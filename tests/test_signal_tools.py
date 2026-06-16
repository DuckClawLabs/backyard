"""Tests for MCP signal tools: signal_ready, wait_for_signal."""

from __future__ import annotations

import json

import pytest

from backyard.server.mcp_hub import signal_tools


PROJECT = "proj-signals"


@pytest.fixture
def auth(alice):
    alice.project_id = PROJECT
    return alice


# ── signal_ready ──────────────────────────────────────────────────────────────

async def test_signal_ready_returns_id(db, auth, fake_redis):
    result = await signal_tools.dispatch(
        "signal_ready",
        {"topic": "user-api", "message": "User service is up"},
        db,
        auth,
    )
    assert "user-api" in result
    assert "published" in result.lower()


async def test_signal_ready_with_payload(db, auth, fake_redis):
    result = await signal_tools.dispatch(
        "signal_ready",
        {
            "topic": "auth-middleware",
            "payload": {"contract_id": "auth-v1", "endpoints": ["/login"]},
            "message": "Auth middleware deployed",
        },
        db,
        auth,
    )
    assert "auth-middleware" in result


async def test_signal_ready_minimal_args(db, auth, fake_redis):
    result = await signal_tools.dispatch(
        "signal_ready",
        {"topic": "db-migrations"},
        db,
        auth,
    )
    assert "db-migrations" in result


# ── wait_for_signal ───────────────────────────────────────────────────────────

async def test_wait_for_signal_already_published(db, auth, fake_redis):
    # Publish first, then wait — should resolve immediately
    await signal_tools.dispatch(
        "signal_ready", {"topic": "frontend-ready"}, db, auth
    )
    result = await signal_tools.dispatch(
        "wait_for_signal", {"topic": "frontend-ready", "timeout": 5}, db, auth
    )
    data = json.loads(result)
    assert data["timed_out"] is False
    assert data["topic"] == "frontend-ready"
    assert data["signal_id"] is not None


async def test_wait_for_signal_timeout(db, auth, fake_redis):
    result = await signal_tools.dispatch(
        "wait_for_signal", {"topic": "never-published", "timeout": 1}, db, auth
    )
    data = json.loads(result)
    assert data["timed_out"] is True
    assert data["topic"] == "never-published"


async def test_wait_for_signal_receives_payload(db, auth, fake_redis):
    await signal_tools.dispatch(
        "signal_ready",
        {
            "topic": "payment-service",
            "payload": {"version": "2.1.0"},
            "message": "Payment service deployed",
        },
        db,
        auth,
    )
    result = await signal_tools.dispatch(
        "wait_for_signal", {"topic": "payment-service", "timeout": 5}, db, auth
    )
    data = json.loads(result)
    assert data["timed_out"] is False
    assert data["payload"] == {"version": "2.1.0"}
    assert data["message"] == "Payment service deployed"


async def test_wait_for_signal_published_by_role(db, auth, fake_redis):
    await signal_tools.dispatch(
        "signal_ready", {"topic": "infra-ready"}, db, auth
    )
    result = await signal_tools.dispatch(
        "wait_for_signal", {"topic": "infra-ready", "timeout": 5}, db, auth
    )
    data = json.loads(result)
    assert data["published_by"] == auth.role  # "backend"


# ── cross-tool: signal + activity ────────────────────────────────────────────

async def test_signal_ready_records_activity(db, auth, fake_redis):
    await signal_tools.dispatch(
        "signal_ready", {"topic": "reporting-api", "message": "done"}, db, auth
    )
    activity = await fake_redis.lrange(f"activity:{PROJECT}", 0, -1)
    assert any("reporting-api" in entry for entry in activity)


# ── unknown tool ──────────────────────────────────────────────────────────────

async def test_unknown_tool(db, auth, fake_redis):
    result = await signal_tools.dispatch("nonexistent_tool", {}, db, auth)
    assert "Unknown tool" in result
