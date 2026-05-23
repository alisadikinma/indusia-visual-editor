"""Add deployments table for Phase 10.2 promote-to-prod tracking.

Revision ID: 0008_deployments
Revises: 0007_train_runs
Create Date: 2026-05-23

One row per `/api/projects/{id}/deploy` invocation. Pins back to the
TrainRun whose weights were promoted and records the outcome of the
multi-step `ais model {add,commit,push}` subprocess sequence (see
`docs/specs/ais-model-push.md`). edges_notified stays null in M10; M11
populates it with per-edge webhook outcomes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0008_deployments"
down_revision: Union[str, None] = "0007_train_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "train_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("train_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("edges_notified", postgresql.JSONB(), nullable=True),
        sa.Column(
            "deployed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','succeeded','failed')",
            name="ck_deployments_status",
        ),
    )
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"])
    op.create_index(
        "ix_deployments_train_run_id", "deployments", ["train_run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_deployments_train_run_id", table_name="deployments")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_table("deployments")
