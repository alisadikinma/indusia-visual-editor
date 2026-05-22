"""Add labels table for Phase 6.2 LSF annotation persistence.

Revision ID: 0005_labels
Revises: 0004_pre_labels
Create Date: 2026-05-23

Stores the raw LS-JSON `result[]` emitted by the M6 canvas onSubmit.
Versioned per (project_id, side) so prior eval-set comparisons and
prompt-engineering regressions can be diffed later. Latest version per
side is what M7 training reads via `derive_inspect_scope`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_labels"
down_revision: Union[str, None] = "0004_pre_labels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "labels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("ls_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("side IN ('top','bottom')", name="ck_labels_side"),
        sa.UniqueConstraint(
            "project_id", "side", "version", name="uq_labels_project_side_version"
        ),
    )
    op.create_index("ix_labels_project_id", "labels", ["project_id"])
    op.create_index("ix_labels_project_side", "labels", ["project_id", "side"])


def downgrade() -> None:
    op.drop_index("ix_labels_project_side", table_name="labels")
    op.drop_index("ix_labels_project_id", table_name="labels")
    op.drop_table("labels")
