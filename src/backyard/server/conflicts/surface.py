"""Conflict surface — create and resolve resolution cards."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backyard.db.models import ResolutionModel
from backyard.protocol.resolutions import ResolutionCard, ResolutionDecision
from backyard.server.context import store as context_store
from backyard.server.redis_client import get_redis


async def create_resolution_card(
    db: AsyncSession,
    project_id: str,
    title: str,
    conflict_a: str,
    conflict_b: str,
    affects: list[str],
    raised_by: str,
    raised_by_role: str,
    agent_read: str = "",
) -> ResolutionCard:
    card_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    row = ResolutionModel(
        id=card_id,
        project_id=project_id,
        title=title,
        conflict_a=conflict_a,
        conflict_b=conflict_b,
        affects=affects,
        agent_read=agent_read,
        raised_by=raised_by,
        raised_by_role=raised_by_role,
        status="open",
        created_at=now,
    )
    db.add(row)
    await db.commit()

    # Add to hot Redis set so it shows in briefings immediately
    redis = get_redis()
    await redis.sadd(f"open_resolutions:{project_id}", card_id)
    await redis.hset(
        f"resolution:{project_id}:{card_id}",
        mapping={
            "title": title,
            "conflict_a": conflict_a,
            "conflict_b": conflict_b,
            "raised_by_role": raised_by_role,
            "created_at": now.isoformat(),
        },
    )

    # Publish event so connected dashboard clients see it immediately
    await redis.publish(
        f"events:{project_id}",
        json.dumps({"type": "resolution_created", "resolution_id": card_id, "title": title}),
    )

    return ResolutionCard(
        id=card_id,
        project_id=project_id,
        title=title,
        conflict_a=conflict_a,
        conflict_b=conflict_b,
        affects=affects,
        agent_read=agent_read,
        raised_by=raised_by,
        raised_by_role=raised_by_role,
        status="open",
        created_at=now,
    )


async def resolve_card(
    db: AsyncSession,
    project_id: str,
    resolution_id: str,
    decision: str,
    decided_by: list[str],
    record_as_adr: bool = False,
    adr_title: str = "",
    adr_affects: list[str] | None = None,
) -> ResolutionDecision:
    from sqlalchemy import select, update

    now = datetime.now(timezone.utc)

    await db.execute(
        update(ResolutionModel)
        .where(ResolutionModel.id == resolution_id)
        .values(status="resolved", decision=decision, decided_by=decided_by, resolved_at=now)
    )
    await db.commit()

    # Remove from hot Redis set
    redis = get_redis()
    await redis.srem(f"open_resolutions:{project_id}", resolution_id)
    await redis.delete(f"resolution:{project_id}:{resolution_id}")

    # Publish resolution event
    await redis.publish(
        f"events:{project_id}",
        json.dumps({"type": "resolution_resolved", "resolution_id": resolution_id, "decision": decision}),
    )

    adr_id: str | None = None
    if record_as_adr and adr_title:
        adr = await context_store.publish_adr(
            db=db,
            project_id=project_id,
            title=adr_title,
            decision=decision,
            affects=adr_affects or [],
            decided_by=decided_by,
        )
        adr_id = adr.id
        await db.execute(
            update(ResolutionModel)
            .where(ResolutionModel.id == resolution_id)
            .values(adr_id=adr_id)
        )
        await db.commit()

    return ResolutionDecision(
        resolution_id=resolution_id,
        decision=decision,
        decided_by=decided_by,
        record_as_adr=record_as_adr,
        resolved_at=now,
    )


async def get_open_cards(db: AsyncSession, project_id: str) -> list[ResolutionCard]:
    from sqlalchemy import select

    result = await db.execute(
        select(ResolutionModel)
        .where(ResolutionModel.project_id == project_id, ResolutionModel.status == "open")
        .order_by(ResolutionModel.created_at.desc())
    )
    return [
        ResolutionCard(
            id=r.id,
            project_id=r.project_id,
            title=r.title,
            conflict_a=r.conflict_a,
            conflict_b=r.conflict_b,
            affects=r.affects,
            agent_read=r.agent_read,
            raised_by=r.raised_by,
            raised_by_role=r.raised_by_role,
            status=r.status,
            created_at=r.created_at,
        )
        for r in result.scalars().all()
    ]
