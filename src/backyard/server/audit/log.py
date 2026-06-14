"""Audit log — append-only, always on."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.db.models import AuditLogModel
from backyard.protocol.audit import AuditEntry


async def append(
    db: AsyncSession,
    project_id: str,
    engineer_id: str,
    role: str,
    session_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    result_summary: str = "",
    latency_ms: int = 0,
    turn_id: str = "",
) -> None:
    now = datetime.now(timezone.utc)
    checksum = AuditLogModel.compute_checksum(
        project_id, engineer_id, now.isoformat(), tool_name
    )
    row = AuditLogModel(
        project_id=project_id,
        engineer_id=engineer_id,
        role=role,
        session_id=session_id,
        turn_id=turn_id,
        timestamp=now,
        tool_name=tool_name,
        arguments_json=arguments,
        result_summary=result_summary,
        latency_ms=latency_ms,
        checksum=checksum,
    )
    db.add(row)
    await db.commit()


async def query(
    db: AsyncSession,
    project_id: str,
    engineer_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditEntry]:
    stmt = (
        select(AuditLogModel)
        .where(AuditLogModel.project_id == project_id)
        .order_by(AuditLogModel.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    if engineer_id:
        stmt = stmt.where(AuditLogModel.engineer_id == engineer_id)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        AuditEntry(
            project_id=row.project_id,
            engineer_id=row.engineer_id,
            role=row.role,
            session_id=row.session_id,
            turn_id=row.turn_id,
            timestamp=row.timestamp,
            tool_name=row.tool_name,
            arguments=row.arguments_json,
            result_summary=row.result_summary,
            latency_ms=row.latency_ms,
        )
        for row in rows
    ]
