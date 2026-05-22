"""Add pre_labels table for Phase 5.2 pre-label assistant persistence.

Revision ID: 0004_pre_labels
Revises: 0003_adapt_runs
Create Date: 2026-05-23

Stores the latest set of pre-label regions per (project_id, side). The
M5 Gemma assistant writes here; the M6 canvas bakes the regions into
the LSF task as `predictions[]` so users open an annotated board.
Latest-wins via UNIQUE(project_id, side); the route layer UPSERTs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_pre_labels"
down_revision: Union[str, None] = "0003_adapt_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pre_labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("regions_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("side IN ('top','bottom')", name="ck_pre_labels_side"),
        sa.UniqueConstraint("project_id", "side", name="uq_pre_labels_project_side"),
    )
    op.create_index("ix_pre_labels_project_id", "pre_labels", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_pre_labels_project_id", table_name="pre_labels")
    op.drop_table("pre_labels")
