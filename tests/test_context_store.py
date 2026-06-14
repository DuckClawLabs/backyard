"""Context store tests — contracts, ADRs, file summaries, search."""

from __future__ import annotations

import pytest

from backyard.server.context.store import (
    get_adrs,
    get_contract,
    get_contracts,
    get_file_summary,
    publish_adr,
    publish_contract,
    search_context,
    upsert_file_summary,
)

PROJECT = "proj-test"
ENG_ID = "alice-id"


@pytest.mark.asyncio
async def test_publish_and_get_contract(db):
    contract = await publish_contract(
        db,
        project_id=PROJECT,
        contract_id="user-api-v1",
        published_by=ENG_ID,
        role="backend",
        content={"endpoints": [{"method": "GET", "path": "/users/:id", "response": "UserDTO"}]},
        description="User profile API",
    )
    assert contract.version == 1
    assert "UserDTO" in str(contract.endpoints)

    fetched = await get_contract(db, PROJECT, "user-api-v1")
    assert fetched is not None
    assert fetched.description == "User profile API"


@pytest.mark.asyncio
async def test_contract_versioning(db):
    await publish_contract(db, PROJECT, "payment-api", ENG_ID, "backend", {}, "v1")
    c2 = await publish_contract(db, PROJECT, "payment-api", ENG_ID, "backend", {}, "v2")
    assert c2.version == 2

    latest = await get_contract(db, PROJECT, "payment-api")
    assert latest.version == 2


@pytest.mark.asyncio
async def test_publish_adr(db):
    adr = await publish_adr(
        db,
        project_id=PROJECT,
        title="Use Postgres for all persistence",
        decision="Postgres",
        affects=["db/**"],
        decided_by=[ENG_ID, "bob-id"],
    )
    assert adr.adr_ref == "ADR-001"
    assert adr.status == "accepted"

    adrs = await get_adrs(db, PROJECT)
    assert len(adrs) == 1
    assert adrs[0].title == "Use Postgres for all persistence"


@pytest.mark.asyncio
async def test_adr_numbering(db):
    await publish_adr(db, PROJECT, "Decision A", "A", ["x/**"], [ENG_ID])
    adr2 = await publish_adr(db, PROJECT, "Decision B", "B", ["y/**"], [ENG_ID])
    assert adr2.adr_ref == "ADR-002"


@pytest.mark.asyncio
async def test_upsert_file_summary(db):
    fs = await upsert_file_summary(
        db, PROJECT, "api/users.py", "Handles user CRUD.", ["get_user", "create_user"], ENG_ID
    )
    assert fs.path == "api/users.py"
    assert "get_user" in fs.exports

    # Upsert again — should update, not insert a duplicate
    fs2 = await upsert_file_summary(
        db, PROJECT, "api/users.py", "Updated summary.", ["get_user"], ENG_ID
    )
    assert fs2.summary == "Updated summary."

    fetched = await get_file_summary(db, PROJECT, "api/users.py")
    assert fetched is not None
    assert fetched.summary == "Updated summary."


@pytest.mark.asyncio
async def test_get_file_summary_missing(db):
    result = await get_file_summary(db, PROJECT, "does/not/exist.py")
    assert result is None


@pytest.mark.asyncio
async def test_search_context(db):
    await publish_contract(db, PROJECT, "auth-api", ENG_ID, "backend", {}, "Auth API")
    await publish_adr(db, PROJECT, "Use Redis for caching", "Redis", ["cache/**"], [ENG_ID])
    await upsert_file_summary(db, PROJECT, "services/auth.py", "Auth service.", [], ENG_ID)

    all_results = await search_context(db, PROJECT)
    types = {r["type"] for r in all_results}
    assert "contract" in types
    assert "adr" in types
    assert "file_summary" in types

    only_contracts = await search_context(db, PROJECT, artifact_type="contract")
    assert all(r["type"] == "contract" for r in only_contracts)
