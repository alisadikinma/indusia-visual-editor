"""Add chat_sessions table for Phase 12.1 chat advisor.

Revision ID: 0010_chat_sessions
Revises: 0009_edges
Create Date: 2026-05-23

One row per operator <-> Gemma advisor session. `messages_json` is a
JSONB array of `{role, content, ts}` turns appended by the streaming SSE
endpoint (Phase 12.3). The auto-update of `updated_at` is enforced at the
ORM layer (Mapped onupdate=func.now()) rather than via a Postgres trigger
to keep migrations simple.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0010_chat_sessions"
down_revision: Union[str, None] = "0009_edges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "messages_json",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chat_sessions_project_id", "chat_sessions", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_project_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
