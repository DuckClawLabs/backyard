"""Signal engine tests — publish, wait, timeout, persistent signal."""

from __future__ import annotations

import asyncio

import pytest

from backyard.server.signals.engine import await_signal, publish_signal

PROJECT = "proj-test"


@pytest.mark.asyncio
async def test_publish_then_wait(db, fake_redis):
    signal = await publish_signal(db, PROJECT, "user-api", "alice-id", "backend", {"contract": "v1"})
    assert signal.topic == "user-api"

    result = await await_signal(db, PROJECT, "user-api", timeout=5)
    assert not result.timed_out
    assert result.signal is not None
    assert result.signal.topic == "user-api"
    assert result.signal.payload == {"contract": "v1"}


@pytest.mark.asyncio
async def test_wait_resolves_with_existing_signal(db, fake_redis):
    await publish_signal(db, PROJECT, "auth-ready", "alice-id", "devops", {})
    # second wait should resolve immediately without any pub/sub
    result = await await_signal(db, PROJECT, "auth-ready", timeout=1)
    assert not result.timed_out


@pytest.mark.asyncio
async def test_wait_timeout(db, fake_redis):
    result = await await_signal(db, PROJECT, "nonexistent-signal", timeout=1)
    assert result.timed_out
    assert result.signal is None


@pytest.mark.asyncio
async def test_publish_unblocks_waiter(db, fake_redis):
    wait_task = asyncio.create_task(await_signal(db, PROJECT, "migration-done", timeout=10))
    await asyncio.sleep(0.05)  # let the subscription establish

    await publish_signal(db, PROJECT, "migration-done", "bob-id", "backend", {"tables": 5})
    result = await asyncio.wait_for(wait_task, timeout=5)

    assert not result.timed_out
    assert result.signal.payload == {"tables": 5}
