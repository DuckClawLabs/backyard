"""Add git_branch column to audit_log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column("git_branch", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_audit_log_branch", "audit_log", ["project_id", "git_branch"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_branch", table_name="audit_log")
    op.drop_column("audit_log", "git_branch")
