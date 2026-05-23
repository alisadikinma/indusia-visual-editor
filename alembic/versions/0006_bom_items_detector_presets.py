"""Add scope_mode + detector_presets to bom_items for Phase 6.6.

Revision ID: 0006_bom_items_detector_presets
Revises: 0005_labels
Create Date: 2026-05-23

The labeling canvas (M6) submit handler runs `derive_inspect_scope` over
the LSF annotation and produces per-region `BomItemUpdate`s with three
fields: inspect_scope (already present), scope_mode, and detector_presets.

scope_mode is per_component for the vast majority of regions; whole_side
is the solder_short escape hatch enforced by the deriver.

detector_presets is a JSONB list of detector names from
data/defect_detector_mapping.yaml — the M4 adapter reads this column to
build the graphflow subgraph per designator. We never store free-form
strings here; the deriver guards via the mapping yaml.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_bom_items_detector_presets"
down_revision: Union[str, None] = "0005_labels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "bom_items",
        sa.Column(
            "scope_mode",
            sa.String(32),
            nullable=False,
            server_default="per_component",
        ),
    )
    op.create_check_constraint(
        "ck_bom_items_scope_mode",
        "bom_items",
        "scope_mode IN ('per_component', 'whole_side')",
    )
    op.add_column(
        "bom_items",
        sa.Column("detector_presets", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bom_items", "detector_presets")
    op.drop_constraint("ck_bom_items_scope_mode", "bom_items", type_="check")
    op.drop_column("bom_items", "scope_mode")
