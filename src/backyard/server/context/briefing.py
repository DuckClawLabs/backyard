"""Project briefing assembly — injected into every agent turn."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backyard.protocol.briefing import (
    ActiveSession,
    BriefingContract,
    OpenDecision,
    ProjectBriefing,
)
from backyard.server.config import settings
from backyard.server.context.store import get_contracts
from backyard.server.redis_client import get_redis


async def get_active_sessions(project_id: str) -> list[ActiveSession]:
    redis = get_redis()
    raw = await redis.hgetall(f"sessions:{project_id}")
    sessions = []
    for engineer_id, data_str in raw.items():
        try:
            data = json.loads(data_str)
            sessions.append(
                ActiveSession(
                    engineer_id=engineer_id,
                    engineer_name=data.get("name", engineer_id),
                    role=data.get("role", "unknown"),
                    connected_since=datetime.fromisoformat(data["connected_since"]),
                )
            )
        except (json.JSONDecodeError, KeyError):
            continue
    return sessions


async def get_recent_activity(project_id: str, limit: int = 5) -> list[str]:
    redis = get_redis()
    bullets = await redis.lrange(f"activity:{project_id}", 0, limit - 1)
    return list(bullets)


async def get_open_decisions(project_id: str) -> list[OpenDecision]:
    redis = get_redis()
    ids = await redis.smembers(f"open_resolutions:{project_id}")
    decisions = []
    for rid in ids:
        raw = await redis.hgetall(f"resolution:{project_id}:{rid}")
        if raw:
            decisions.append(
                OpenDecision(
                    resolution_id=rid,
                    title=raw.get("title", "Unnamed conflict"),
                    created_at=datetime.fromisoformat(
                        raw.get("created_at", datetime.now(timezone.utc).isoformat())
                    ),
                )
            )
    return decisions


async def assemble_briefing(
    db: AsyncSession,
    project_id: str,
    project_name: str,
    engineer_id: str,
    role: str,
) -> ProjectBriefing:
    active = await get_active_sessions(project_id)
    activity = await get_recent_activity(project_id)
    open_decisions = await get_open_decisions(project_id)
    contracts = await get_contracts(db, project_id)

    briefing_contracts = [
        BriefingContract(
            contract_id=c.contract_id or c.id,
            description=c.description or f"Contract {c.contract_id or c.id}",
            published_by_role=c.published_by_role,
            published_at=c.created_at,
        )
        for c in contracts
    ]

    briefing = ProjectBriefing(
        project_id=project_id,
        project_name=project_name,
        my_role=role,
        active_sessions=[s for s in active if s.engineer_id != engineer_id],
        recent_activity=activity,
        contracts=briefing_contracts,
        open_decisions=open_decisions,
    )

    # Trim to token budget (rough estimate: 1 token ≈ 4 chars)
    rendered = briefing.render()
    while len(rendered) > settings.briefing_max_tokens * 4 and briefing.recent_activity:
        briefing.recent_activity.pop()
        rendered = briefing.render()

    return briefing


async def record_activity(project_id: str, bullet: str) -> None:
    """Prepend an activity bullet to the project's hot activity list."""
    redis = get_redis()
    await redis.lpush(f"activity:{project_id}", bullet)
    await redis.ltrim(f"activity:{project_id}", 0, 49)   # keep last 50
