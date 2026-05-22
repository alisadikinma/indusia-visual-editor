"""Initial schema: projects, assets, bom_items.

Revision ID: 0001_initial
Revises: (none)
Create Date: 2026-05-22

Brings the database to the state documented in
`docs/plans/2026-05-22-visual-editor-mvp.md` §5.3 and CLAUDE.md §7.
Enums use CHECK constraints (native_enum=False in the ORM) — no CREATE TYPE
ordering pain and no manual DROP TYPE on downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            sa.CheckConstraint(
                "status IN ('drafting','training','deployed','failed')",
                name="ck_projects_status",
            ),
            nullable=False,
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
        sa.UniqueConstraint("slug", name="uq_projects_slug"),
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(32),
            sa.CheckConstraint(
                "kind IN ('bom','golden_top','golden_bottom','drawing')",
                name="ck_assets_kind",
            ),
            nullable=False,
        ),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime", sa.String(127), nullable=True),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index("ix_assets_sha256", "assets", ["sha256"])

    op.create_table(
        "bom_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("designator", sa.String(64), nullable=False),
        sa.Column("value", sa.String(255), nullable=True),
        sa.Column("package", sa.String(127), nullable=True),
        sa.Column("qty", sa.Integer, nullable=True),
        sa.Column("position_hint", sa.String(255), nullable=True),
        sa.Column(
            "inspect_scope",
            sa.String(32),
            sa.CheckConstraint(
                "inspect_scope IN ('pending','inspected','skipped')",
                name="ck_bom_items_inspect_scope",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("mi_likely", sa.Boolean, nullable=True),
        sa.Column("component_type", sa.String(64), nullable=True),
        sa.Column(
            "defect_history_count",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("extra", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_bom_items_project_id", "bom_items", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_bom_items_project_id", table_name="bom_items")
    op.drop_table("bom_items")
    op.drop_index("ix_assets_sha256", table_name="assets")
    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_table("assets")
    op.drop_table("projects")
