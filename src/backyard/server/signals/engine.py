"""Signal engine — Redis pub/sub for signal_ready / wait_for_signal.

Signals are branch-scoped by default: a signal published on feature/checkout
only unblocks waiters on feature/checkout.

Pass scope="project" to publish/await a signal that crosses all branches —
useful for infra-level milestones that affect the whole team.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.db.models import SignalModel
from backyard.protocol.signals import Signal, WaitResult
from backyard.server.redis_client import get_redis

_PROJECT_SCOPE = "_project_"


def _branch_channel(project_id: str, git_branch: str, topic: str) -> str:
    return f"signals:{project_id}:{git_branch}:{topic}"


def _project_channel(project_id: str, topic: str) -> str:
    return f"signals:{project_id}:{_PROJECT_SCOPE}:{topic}"


async def publish_signal(
    db: AsyncSession,
    project_id: str,
    topic: str,
    engineer_id: str,
    role: str,
    git_branch: str,
    payload: dict,
    message: str = "",
    scope: str = "branch",   # "branch" | "project"
) -> Signal:
    effective_branch = _PROJECT_SCOPE if scope == "project" else git_branch

    signal = Signal(
        id=str(uuid.uuid4()),
        project_id=project_id,
        topic=topic,
        published_by=engineer_id,
        published_by_role=role,
        git_branch=effective_branch,
        payload=payload,
        message=message,
        created_at=datetime.now(timezone.utc),
    )

    row = SignalModel(
        id=signal.id,
        project_id=signal.project_id,
        topic=signal.topic,
        git_branch=effective_branch,
        published_by=signal.published_by,
        published_by_role=signal.published_by_role,
        payload_json=signal.payload,
        message=signal.message,
        created_at=signal.created_at,
    )
    db.add(row)
    await db.commit()

    redis = get_redis()
    if scope == "project":
        await redis.publish(_project_channel(project_id, topic), signal.model_dump_json())
    else:
        await redis.publish(_branch_channel(project_id, git_branch, topic), signal.model_dump_json())

    return signal


async def await_signal(
    db: AsyncSession,
    project_id: str,
    topic: str,
    git_branch: str,
    timeout: int = 300,
) -> WaitResult:
    # Check Postgres first — return immediately if signal already exists
    # Match either a branch-specific signal or a project-scoped one.
    result = await db.execute(
        select(SignalModel)
        .where(
            SignalModel.project_id == project_id,
            SignalModel.topic == topic,
            or_(
                SignalModel.git_branch == git_branch,
                SignalModel.git_branch == _PROJECT_SCOPE,
            ),
        )
        .order_by(SignalModel.created_at.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return WaitResult(
            timed_out=False,
            signal=Signal(
                id=existing.id,
                project_id=existing.project_id,
                topic=existing.topic,
                published_by=existing.published_by,
                published_by_role=existing.published_by_role,
                git_branch=existing.git_branch,
                payload=existing.payload_json,
                message=existing.message,
                created_at=existing.created_at,
            ),
        )

    # Subscribe to both the branch channel and the project-wide channel.
    redis = get_redis()
    pubsub = redis.pubsub()
    branch_ch = _branch_channel(project_id, git_branch, topic)
    project_ch = _project_channel(project_id, topic)
    await pubsub.subscribe(branch_ch, project_ch)

    try:
        deadline = asyncio.get_event_loop().time() + timeout
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                return WaitResult(timed_out=False, signal=Signal(**data))
            if asyncio.get_event_loop().time() >= deadline:
                break
    except asyncio.TimeoutError:
        pass
    finally:
        await pubsub.unsubscribe(branch_ch, project_ch)
        await pubsub.aclose()

    return WaitResult(timed_out=True)
