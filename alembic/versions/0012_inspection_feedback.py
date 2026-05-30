"""Add inspection_feedback + defect_examples (v1 inspection-feedback loop).

Revision ID: 0012_inspection_feedback
Revises: 0011_auth
Create Date: 2026-05-30

Two tables for the runtime feedback loop:

  - `inspection_feedback`: operator verdicts on deployed-model detections
    (confirmed / escape / overkill) with the model's own verdict, optional
    ROI crop, and the assigned defect criterion. edge_id / train_run_id are
    SET NULL on parent delete so audit rows survive; project delete cascades.
  - `defect_examples`: curated training samples distilled from a promotable
    feedback row (real missed defect + valid criterion + stored ROI).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0012_inspection_feedback"
down_revision: Union[str, None] = "0011_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inspection_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "edge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("edges.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "train_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("train_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("designator", sa.String(32), nullable=True),
        sa.Column("model_verdict", sa.String(16), nullable=False),
        sa.Column("operator_mark", sa.String(16), nullable=False),
        sa.Column("defect_criterion", sa.String(40), nullable=True),
        sa.Column("roi_path", sa.Text(), nullable=True),
        sa.Column("roi_sha256", sa.String(64), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="new",
        ),
        sa.Column("inspection_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "model_verdict IN ('pass','fail','uncertain')",
            name="ck_inspection_feedback_verdict",
        ),
        sa.CheckConstraint(
            "operator_mark IN ('confirmed','escape','overkill')",
            name="ck_inspection_feedback_mark",
        ),
        sa.CheckConstraint(
            "status IN ('new','curated','promoted','dismissed')",
            name="ck_inspection_feedback_status",
        ),
    )
    op.create_index(
        "ix_inspection_feedback_project_id",
        "inspection_feedback",
        ["project_id"],
    )

    op.create_table(
        "defect_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_feedback_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inspection_feedback.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("designator", sa.String(32), nullable=True),
        sa.Column("defect_criterion", sa.String(40), nullable=False),
        sa.Column("roi_path", sa.Text(), nullable=False),
        sa.Column("roi_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_defect_examples_project_id",
        "defect_examples",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_defect_examples_project_id", table_name="defect_examples")
    op.drop_table("defect_examples")
    op.drop_index(
        "ix_inspection_feedback_project_id", table_name="inspection_feedback"
    )
    op.drop_table("inspection_feedback")
