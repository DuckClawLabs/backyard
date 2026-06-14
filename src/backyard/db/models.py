"""SQLAlchemy ORM models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backyard.server.db import Base


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="team")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    engineers: Mapped[list[Engineer]] = relationship("Engineer", back_populates="org")
    projects: Mapped[list[Project]] = relationship("Project", back_populates="org")


class Engineer(Base):
    __tablename__ = "engineers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("orgs.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    org: Mapped[Org] = relationship("Org", back_populates="engineers")
    tokens: Mapped[list[ApiToken]] = relationship("ApiToken", back_populates="engineer")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    engineer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("engineers.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    engineer: Mapped[Engineer] = relationship("Engineer", back_populates="tokens")

    @staticmethod
    def hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    org_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("orgs.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    git_remote: Mapped[str | None] = mapped_column(Text, unique=True)   # e.g. "github.com/acme/payments"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    org: Mapped[Org] = relationship("Org", back_populates="projects")
    members: Mapped[list[ProjectMember]] = relationship("ProjectMember", back_populates="project")


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), primary_key=True
    )
    engineer_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("engineers.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship("Project", back_populates="members")


class ContractModel(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False
    )
    contract_id: Mapped[str] = mapped_column(Text, nullable=False)
    published_by: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ADRModel(Base):
    __tablename__ = "adrs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False
    )
    adr_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="accepted")
    affects: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    decided_by: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FileSummaryModel(Base):
    __tablename__ = "file_summaries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    exports: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    last_modified_by: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    last_modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SignalModel(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    published_by: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    published_by_role: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResolutionModel(Base):
    __tablename__ = "resolutions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    conflict_a: Mapped[str] = mapped_column(Text, nullable=False)
    conflict_b: Mapped[str] = mapped_column(Text, nullable=False)
    affects: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    agent_read: Mapped[str] = mapped_column(Text, default="")
    raised_by: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    raised_by_role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open")
    decision: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    adr_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivityLogModel(Base):
    __tablename__ = "activity_log"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("projects.id"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bullets: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLogModel(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    engineer_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    turn_id: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)

    @staticmethod
    def compute_checksum(
        project_id: str, engineer_id: str, timestamp: str, tool_name: str
    ) -> str:
        raw = f"{project_id}:{engineer_id}:{timestamp}:{tool_name}"
        return hashlib.sha256(raw.encode()).hexdigest()
