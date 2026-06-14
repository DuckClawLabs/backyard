"""Shared context store — contracts, ADRs, file summaries."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.db.models import ADRModel, ContractModel, FileSummaryModel
from backyard.protocol.artifacts import ADR, Contract, FileSummary


# ── Contracts ─────────────────────────────────────────────────────────────────

async def publish_contract(
    db: AsyncSession,
    project_id: str,
    contract_id: str,
    published_by: str,
    role: str,
    content: dict[str, Any],
    description: str = "",
) -> Contract:
    # Get next version number
    result = await db.execute(
        select(ContractModel.version)
        .where(ContractModel.project_id == project_id, ContractModel.contract_id == contract_id)
        .order_by(ContractModel.version.desc())
        .limit(1)
    )
    last_version = result.scalar_one_or_none() or 0

    row = ContractModel(
        id=str(uuid.uuid4()),
        project_id=project_id,
        contract_id=contract_id,
        published_by=published_by,
        role=role,
        version=last_version + 1,
        content_json=content,
        description=description,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return _contract_from_row(row)


async def get_contracts(db: AsyncSession, project_id: str) -> list[Contract]:
    result = await db.execute(
        select(ContractModel)
        .where(ContractModel.project_id == project_id)
        .order_by(ContractModel.created_at.desc())
    )
    return [_contract_from_row(r) for r in result.scalars().all()]


async def get_contract(db: AsyncSession, project_id: str, contract_id: str) -> Contract | None:
    result = await db.execute(
        select(ContractModel)
        .where(ContractModel.project_id == project_id, ContractModel.contract_id == contract_id)
        .order_by(ContractModel.version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return _contract_from_row(row) if row else None


def _contract_from_row(row: ContractModel) -> Contract:
    return Contract(
        id=row.id,
        contract_id=row.contract_id,
        project_id=row.project_id,
        published_by_role=row.role,
        published_by_engineer=row.published_by,
        version=row.version,
        endpoints=row.content_json.get("endpoints", []),
        types=row.content_json.get("types", {}),
        description=row.description,
        created_at=row.created_at,
    )


# ── ADRs ──────────────────────────────────────────────────────────────────────

async def publish_adr(
    db: AsyncSession,
    project_id: str,
    title: str,
    decision: str,
    affects: list[str],
    decided_by: list[str],
    rationale: str = "",
) -> ADR:
    # Auto-number: ADR-001, ADR-002, …
    result = await db.execute(
        select(ADRModel).where(ADRModel.project_id == project_id).order_by(ADRModel.created_at)
    )
    count = len(result.scalars().all())
    adr_ref = f"ADR-{count + 1:03d}"

    row = ADRModel(
        id=str(uuid.uuid4()),
        project_id=project_id,
        adr_ref=adr_ref,
        title=title,
        status="accepted",
        affects=affects,
        decision=decision,
        rationale=rationale,
        decided_by=decided_by,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    return ADR(
        id=row.id,
        project_id=row.project_id,
        adr_ref=row.adr_ref,
        title=row.title,
        status=row.status,
        affects=row.affects,
        decision=row.decision,
        rationale=row.rationale,
        decided_by=row.decided_by,
        created_at=row.created_at,
    )


async def get_adrs(db: AsyncSession, project_id: str) -> list[ADR]:
    result = await db.execute(
        select(ADRModel)
        .where(ADRModel.project_id == project_id)
        .order_by(ADRModel.created_at)
    )
    return [
        ADR(
            id=r.id,
            project_id=r.project_id,
            adr_ref=r.adr_ref,
            title=r.title,
            status=r.status,
            affects=r.affects,
            decision=r.decision,
            rationale=r.rationale,
            decided_by=r.decided_by,
            created_at=r.created_at,
        )
        for r in result.scalars().all()
    ]


# ── File summaries ────────────────────────────────────────────────────────────

async def upsert_file_summary(
    db: AsyncSession,
    project_id: str,
    path: str,
    summary: str,
    exports: list[str],
    engineer_id: str,
    git_branch: str = "",
) -> FileSummary:
    result = await db.execute(
        select(FileSummaryModel).where(
            FileSummaryModel.project_id == project_id,
            FileSummaryModel.git_branch == git_branch,
            FileSummaryModel.path == path,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if row:
        row.summary = summary
        row.exports = exports
        row.last_modified_by = engineer_id
        row.last_modified_at = now
    else:
        row = FileSummaryModel(
            id=str(uuid.uuid4()),
            project_id=project_id,
            git_branch=git_branch,
            path=path,
            summary=summary,
            exports=exports,
            last_modified_by=engineer_id,
            last_modified_at=now,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)

    return _file_summary_from_row(row)


async def get_file_summary(
    db: AsyncSession, project_id: str, path: str
) -> FileSummary | None:
    result = await db.execute(
        select(FileSummaryModel)
        .where(
            FileSummaryModel.project_id == project_id,
            FileSummaryModel.path == path,
        )
        .order_by(FileSummaryModel.last_modified_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return _file_summary_from_row(row) if row else None


def _file_summary_from_row(row: FileSummaryModel) -> FileSummary:
    return FileSummary(
        id=row.id,
        project_id=row.project_id,
        git_branch=row.git_branch,
        path=row.path,
        summary=row.summary,
        exports=row.exports,
        last_modified_by=row.last_modified_by,
        last_modified_at=row.last_modified_at,
    )


async def search_context(
    db: AsyncSession,
    project_id: str,
    artifact_type: str | None = None,
    role: str | None = None,
    path_prefix: str | None = None,
) -> list[dict]:
    results: list[dict] = []

    if artifact_type in (None, "contract"):
        stmt = select(ContractModel).where(ContractModel.project_id == project_id)
        if role:
            stmt = stmt.where(ContractModel.role == role)
        rows = (await db.execute(stmt)).scalars().all()
        for r in rows:
            results.append({
                "type": "contract",
                "id": r.contract_id,
                "summary": r.description or f"Contract {r.contract_id} v{r.version}",
                "published_by_role": r.role,
                "created_at": r.created_at.isoformat(),
            })

    if artifact_type in (None, "adr"):
        rows = (await db.execute(
            select(ADRModel).where(ADRModel.project_id == project_id)
        )).scalars().all()
        for r in rows:
            results.append({
                "type": "adr",
                "id": r.adr_ref,
                "summary": f"{r.title}: {r.decision[:120]}",
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            })

    if artifact_type in (None, "file_summary"):
        stmt = select(FileSummaryModel).where(
            FileSummaryModel.project_id == project_id,
        )
        if path_prefix:
            stmt = stmt.where(FileSummaryModel.path.startswith(path_prefix))
        rows = (await db.execute(stmt)).scalars().all()
        for r in rows:
            results.append({
                "type": "file_summary",
                "id": r.path,
                "git_branch": r.git_branch,
                "summary": r.summary,
                "exports": r.exports,
                "last_modified_by": r.last_modified_by,
                "last_modified_at": r.last_modified_at.isoformat(),
            })

    return results
