"""Add edges table for Phase 11.1 edge registry.

Revision ID: 0009_edges
Revises: 0008_deployments
Create Date: 2026-05-23

Edge nodes register once via POST /api/edges; the visual-editor stores
their webhook URL + version_policy here. On a successful M10 deployment
the notify service (Phase 11.2) fans out a webhook to every registered
edge, gated by the per-edge policy.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0009_edges"
down_revision: Union[str, None] = "0008_deployments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column(
            "version_policy",
            postgresql.JSONB(),
            nullable=False,
            server_default='{"mode": "auto_pull_latest"}',
        ),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_edges_name"),
    )


def downgrade() -> None:
    op.drop_table("edges")
