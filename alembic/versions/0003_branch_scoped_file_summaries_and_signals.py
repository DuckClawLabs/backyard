"""Branch-scope file_summaries and signals.

file_summaries: add git_branch column; unique constraint changes from
(project_id, path) to (project_id, git_branch, path) so each branch
has its own copy of every file summary.

signals: add git_branch column so persistent signal lookup can filter
by branch. "_project_" is the sentinel value for project-scoped signals.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── file_summaries ────────────────────────────────────────────────────────
    op.add_column(
        "file_summaries",
        sa.Column("git_branch", sa.Text, nullable=False, server_default=""),
    )
    # Drop the old (project_id, path) unique constraint
    op.drop_constraint("uq_file_summaries_project_path", "file_summaries", type_="unique")
    # Add the new (project_id, git_branch, path) unique constraint
    op.create_unique_constraint(
        "uq_file_summaries_project_branch_path",
        "file_summaries",
        ["project_id", "git_branch", "path"],
    )

    # ── signals ───────────────────────────────────────────────────────────────
    op.add_column(
        "signals",
        sa.Column("git_branch", sa.Text, nullable=False, server_default=""),
    )
    # Re-create index to include branch for efficient per-branch lookup
    op.drop_index("ix_signals_project_topic", table_name="signals")
    op.create_index(
        "ix_signals_project_branch_topic",
        "signals",
        ["project_id", "git_branch", "topic"],
    )


def downgrade() -> None:
    op.drop_index("ix_signals_project_branch_topic", table_name="signals")
    op.create_index("ix_signals_project_topic", "signals", ["project_id", "topic"])
    op.drop_column("signals", "git_branch")

    op.drop_constraint("uq_file_summaries_project_branch_path", "file_summaries", type_="unique")
    op.create_unique_constraint(
        "uq_file_summaries_project_path", "file_summaries", ["project_id", "path"]
    )
    op.drop_column("file_summaries", "git_branch")
