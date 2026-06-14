"""Shared test fixtures."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backyard.server.db import Base
import backyard.db.models  # noqa: F401


# ── In-memory Postgres (SQLite for unit tests) ─────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


# ── Fake Redis ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def fake_redis(monkeypatch):
    redis = FakeRedis(decode_responses=True)
    import backyard.server.redis_client as rc
    monkeypatch.setattr(rc, "_redis", redis)
    yield redis
    await redis.aclose()


# ── Auth context ──────────────────────────────────────────────────────────────

@pytest.fixture
def alice():
    from backyard.server.auth import AuthContext
    return AuthContext(
        engineer_id="alice-id",
        engineer_name="alice",
        org_id="org-1",
        role="backend",
        session_id="session-alice",
    )


@pytest.fixture
def bob():
    from backyard.server.auth import AuthContext
    return AuthContext(
        engineer_id="bob-id",
        engineer_name="bob",
        org_id="org-1",
        role="frontend",
        session_id="session-bob",
    )
