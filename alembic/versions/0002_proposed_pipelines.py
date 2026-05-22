"""Add proposed_pipelines table for Phase 3.4 planner persistence.

Revision ID: 0002_proposed_pipelines
Revises: 0001_initial
Create Date: 2026-05-22

Stores versioned LLM planner output per project. Latest version wins
for downstream M4 adapter, but history is kept so prompt regressions
can be diffed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002_proposed_pipelines"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proposed_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("dag_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "project_id", "version", name="uq_proposed_pipelines_project_version"
        ),
    )
    op.create_index(
        "ix_proposed_pipelines_project_id",
        "proposed_pipelines",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_proposed_pipelines_project_id", table_name="proposed_pipelines")
    op.drop_table("proposed_pipelines")
