"""Add organizations + users + projects.organization_id (Phase 13.1).

Revision ID: 0011_auth
Revises: 0010_chat_sessions
Create Date: 2026-05-24

Single migration adds both tenancy tables AND the FK on projects, then
back-fills `projects.organization_id` to a seed organization row so v1
single-tenant deploys keep working. The column stays nullable in v1 because
M14 production migration to multi-tenant will pivot it to NOT NULL once all
existing rows are guaranteed to be associated; right now it is "soft FK".
"""

from typing import Sequence, Union
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011_auth"
down_revision: Union[str, None] = "0010_chat_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
SEED_ORG_SLUG = "default"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.String(16),
            sa.CheckConstraint(
                "role IN ('admin','engineer','viewer')",
                name="ck_users_role",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    op.add_column(
        "projects",
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_projects_organization_id",
        source_table="projects",
        referent_table="organizations",
        local_cols=["organization_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_projects_organization_id", "projects", ["organization_id"]
    )

    # Seed default organization and back-fill existing projects so v1
    # single-tenant installs keep returning their rows for the seed user.
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at) "
            "VALUES (:id, :name, :slug, now())"
        ).bindparams(id=SEED_ORG_ID, name="Default", slug=SEED_ORG_SLUG)
    )
    op.execute(
        sa.text("UPDATE projects SET organization_id = :id").bindparams(
            id=SEED_ORG_ID
        )
    )


def downgrade() -> None:
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_constraint(
        "fk_projects_organization_id", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "organization_id")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
