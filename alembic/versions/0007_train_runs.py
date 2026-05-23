"""Add train_runs table for Phase 7.2 training job tracking.

Revision ID: 0007_train_runs
Revises: 0006_bom_items_detector_presets
Create Date: 2026-05-23

One row per `/api/projects/{id}/training/start` invocation. Pins back to
the AdaptRun that produced the model_dir (so the lineage from BOM →
graphflow tree → training job is reproducible) and to the
auto-inspect-service `job_id` (so the SSE relay can be re-attached).
Terminal metrics land in `metrics_json` on the succeeded event; transport
or service failures land in `error_text`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0007_train_runs"
down_revision: Union[str, None] = "0006_bom_items_detector_presets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "train_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "adapt_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("adapt_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("service_job_id", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("metrics_json", postgresql.JSONB(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="ck_train_runs_status",
        ),
    )
    op.create_index("ix_train_runs_project_id", "train_runs", ["project_id"])
    op.create_index(
        "ix_train_runs_service_job_id", "train_runs", ["service_job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_train_runs_service_job_id", table_name="train_runs")
    op.drop_index("ix_train_runs_project_id", table_name="train_runs")
    op.drop_table("train_runs")
