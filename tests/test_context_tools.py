"""Tests for MCP context tools: query_shared_context, publish_context, get_file_summary, get_project_status."""

from __future__ import annotations

import json

import pytest

from backyard.server.mcp_hub import context_tools
from backyard.server.context import store


PROJECT = "proj-ctx"


@pytest.fixture
def auth(alice):
    alice.project_id = PROJECT
    return alice


# ── query_shared_context ──────────────────────────────────────────────────────

async def test_query_shared_context_empty(db, auth):
    result = await context_tools.dispatch("query_shared_context", {"query": "anything"}, db, auth)
    assert result == "No matching context found."


async def test_query_shared_context_finds_contract(db, auth):
    await store.publish_contract(
        db,
        project_id=PROJECT,
        contract_id="user-api-v1",
        published_by=auth.engineer_id,
        role="backend",
        content={"endpoints": [{"method": "GET", "path": "/users", "response": "User[]"}]},
        description="User API",
    )
    result = await context_tools.dispatch(
        "query_shared_context", {"query": "user", "type": "contract"}, db, auth
    )
    data = json.loads(result)
    assert any(item["id"] == "user-api-v1" for item in data)


async def test_query_shared_context_finds_adr(db, auth):
    await store.publish_adr(
        db,
        project_id=PROJECT,
        title="Use PostgreSQL",
        decision="PostgreSQL over MySQL for JSONB support",
        affects=["db/**"],
        decided_by=[auth.engineer_id],
    )
    result = await context_tools.dispatch(
        "query_shared_context", {"query": "database", "type": "adr"}, db, auth
    )
    data = json.loads(result)
    assert any(item["type"] == "adr" for item in data)


async def test_query_shared_context_type_filter_excludes_others(db, auth):
    await store.publish_contract(
        db,
        project_id=PROJECT,
        contract_id="payment-api",
        published_by=auth.engineer_id,
        role="backend",
        content={},
        description="",
    )
    result = await context_tools.dispatch(
        "query_shared_context", {"query": "payment", "type": "adr"}, db, auth
    )
    assert result == "No matching context found."


# ── publish_context ───────────────────────────────────────────────────────────

async def test_publish_context_contract(db, auth):
    result = await context_tools.dispatch(
        "publish_context",
        {
            "type": "contract",
            "id": "auth-api-v1",
            "content": {
                "endpoints": [
                    {"method": "POST", "path": "/login", "response": "Token"},
                    {"method": "POST", "path": "/logout", "response": "void"},
                ],
            },
            "description": "Auth API contract",
        },
        db,
        auth,
    )
    assert "auth-api-v1" in result
    assert "v1" in result


async def test_publish_context_contract_versioning(db, auth):
    for _ in range(3):
        await context_tools.dispatch(
            "publish_context",
            {"type": "contract", "id": "orders-api", "content": {}, "description": ""},
            db,
            auth,
        )
    result = await context_tools.dispatch(
        "publish_context",
        {"type": "contract", "id": "orders-api", "content": {}, "description": ""},
        db,
        auth,
    )
    assert "v4" in result


async def test_publish_context_adr(db, auth):
    result = await context_tools.dispatch(
        "publish_context",
        {
            "type": "adr",
            "id": "adr-redis-cache",
            "content": {
                "decision": "Use Redis for caching",
                "rationale": "Low latency reads",
                "affects": ["services/**"],
            },
            "description": "Redis caching decision",
        },
        db,
        auth,
    )
    assert "ADR-" in result
    assert "Redis caching decision" in result


async def test_publish_context_unknown_type(db, auth):
    result = await context_tools.dispatch(
        "publish_context",
        {"type": "unknown", "id": "x", "content": {}},
        db,
        auth,
    )
    assert "Unknown artifact type" in result


# ── get_file_summary ──────────────────────────────────────────────────────────

async def test_get_file_summary_missing(db, auth):
    result = await context_tools.dispatch(
        "get_file_summary", {"path": "src/nonexistent.py"}, db, auth
    )
    assert "No summary available" in result


async def test_get_file_summary_existing(db, auth):
    await store.upsert_file_summary(
        db,
        project_id=PROJECT,
        path="src/users.py",
        summary="Handles user CRUD operations.",
        exports=["UserService", "create_user"],
        engineer_id=auth.engineer_id,
    )
    result = await context_tools.dispatch(
        "get_file_summary", {"path": "src/users.py"}, db, auth
    )
    data = json.loads(result)
    assert data["path"] == "src/users.py"
    assert data["summary"] == "Handles user CRUD operations."
    assert "UserService" in data["exports"]


# ── get_project_status ────────────────────────────────────────────────────────

async def test_get_project_status_empty(db, auth, fake_redis):
    result = await context_tools.dispatch("get_project_status", {}, db, auth)
    data = json.loads(result)
    assert "active_sessions" in data
    assert "contracts" in data
    assert "open_decisions" in data
    assert isinstance(data["open_decisions"], int)


async def test_get_project_status_includes_contracts(db, auth, fake_redis):
    await store.publish_contract(
        db,
        project_id=PROJECT,
        contract_id="inventory-api",
        published_by=auth.engineer_id,
        role="backend",
        content={},
        description="Inventory service contract",
    )
    result = await context_tools.dispatch("get_project_status", {}, db, auth)
    data = json.loads(result)
    assert any(c["id"] == "inventory-api" for c in data["contracts"])


async def test_unknown_tool(db, auth):
    result = await context_tools.dispatch("nonexistent_tool", {}, db, auth)
    assert "Unknown tool" in result
