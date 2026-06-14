"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-06-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orgs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default="team"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "engineers",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "api_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("engineer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("engineers.id"), nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_members",
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("engineer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("engineers.id"), primary_key=True),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("contract_id", sa.Text, nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("content_json", postgresql.JSONB, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "adrs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("adr_ref", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="accepted"),
        sa.Column("affects", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, server_default=""),
        sa.Column("decided_by", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "file_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("exports", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("last_modified_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("last_modified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "path", name="uq_file_summaries_project_path"),
    )

    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("published_by_role", sa.String(64), nullable=False),
        sa.Column("payload_json", postgresql.JSONB, server_default="{}"),
        sa.Column("message", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_signals_project_topic", "signals", ["project_id", "topic"])

    op.create_table(
        "resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("conflict_a", sa.Text, nullable=False),
        sa.Column("conflict_b", sa.Text, nullable=False),
        sa.Column("affects", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("agent_read", sa.Text, server_default=""),
        sa.Column("raised_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("raised_by_role", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("decision", sa.Text),
        sa.Column("decided_by", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("adr_id", postgresql.UUID(as_uuid=False)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "activity_log",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bullets", postgresql.ARRAY(sa.Text), nullable=False, server_default="{}"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("engineer_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("turn_id", sa.Text, server_default=""),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("tool_name", sa.Text, nullable=False),
        sa.Column("arguments_json", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result_summary", sa.Text, server_default=""),
        sa.Column("latency_ms", sa.Integer, server_default="0"),
        sa.Column("checksum", sa.Text, nullable=False),
    )
    op.create_index("ix_audit_log_project_timestamp", "audit_log", ["project_id", "timestamp"])
    op.create_index("ix_audit_log_engineer", "audit_log", ["engineer_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("activity_log")
    op.drop_table("resolutions")
    op.drop_table("signals")
    op.drop_table("file_summaries")
    op.drop_table("adrs")
    op.drop_table("contracts")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("api_tokens")
    op.drop_table("engineers")
    op.drop_table("orgs")
