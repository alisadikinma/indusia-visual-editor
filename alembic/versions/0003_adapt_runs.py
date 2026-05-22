"""Add adapt_runs table for Phase 4.6 adapter route history.

Revision ID: 0003_adapt_runs
Revises: 0002_proposed_pipelines
Create Date: 2026-05-22

Records each invocation of the planner adapter. The route layer
(POST /api/projects/{id}/adapt) writes one row per successful compose,
so the operator can audit which graphflow model dirs were emitted from
which project state, without needing to scan the filesystem.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_adapt_runs"
down_revision: Union[str, None] = "0002_proposed_pipelines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "adapt_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pcb_name", sa.String(255), nullable=False),
        sa.Column("model_dir", sa.Text(), nullable=False),
        sa.Column("inspected_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            server_default="ok",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ok','failed')", name="ck_adapt_runs_status"
        ),
    )
    op.create_index(
        "ix_adapt_runs_project_id", "adapt_runs", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_adapt_runs_project_id", table_name="adapt_runs")
    op.drop_table("adapt_runs")
