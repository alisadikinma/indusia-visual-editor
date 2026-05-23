"""SQLAlchemy 2.x declarative models for Phase 1.1.

Schema mirrors `docs/plans/2026-05-22-visual-editor-mvp.md` §5.3 and CLAUDE.md
§7. Enums emit CHECK constraints (native_enum=False) — keeps migrations simple
and avoids the "CREATE TYPE before column" ordering pain.

Adding a new table? Update both the design doc, CLAUDE.md §7, AND generate an
Alembic migration with `alembic revision --autogenerate -m "..."`.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProjectStatus(str, enum.Enum):
    DRAFTING = "drafting"
    TRAINING = "training"
    DEPLOYED = "deployed"
    FAILED = "failed"


class AssetKind(str, enum.Enum):
    BOM = "bom"
    GOLDEN_TOP = "golden_top"
    GOLDEN_BOTTOM = "golden_bottom"
    DRAWING = "drawing"


class InspectScope(str, enum.Enum):
    PENDING = "pending"
    INSPECTED = "inspected"
    SKIPPED = "skipped"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            name="project_status",
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=ProjectStatus.DRAFTING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    assets: Mapped[list["Asset"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    bom_items: Mapped[list["BomItem"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    proposed_pipelines: Mapped[list["ProposedPipelineRow"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    adapt_runs: Mapped[list["AdaptRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pre_labels: Mapped[list["PreLabel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    labels: Mapped[list["Label"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    train_runs: Mapped[list["TrainRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (UniqueConstraint("slug", name="uq_projects_slug"),)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AssetKind] = mapped_column(
        Enum(
            AssetKind,
            name="asset_kind",
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime: Mapped[str | None] = mapped_column(String(127), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="assets")


class BomItem(Base):
    __tablename__ = "bom_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    designator: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    package: Mapped[str | None] = mapped_column(String(127), nullable=True)
    qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_hint: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Scope (user-controlled in canvas — see plan §1.5 + §5.3)
    inspect_scope: Mapped[InspectScope] = mapped_column(
        Enum(
            InspectScope,
            name="inspect_scope",
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=InspectScope.PENDING,
        server_default=InspectScope.PENDING.value,
    )
    mi_likely: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    component_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    defect_history_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # M6 Phase 6.6 — derived from the canvas annotation by
    # services/inspect_scope/derive.derive_inspect_scope and persisted by
    # POST /api/projects/{id}/labels. scope_mode is per_component for the
    # vast majority of regions; whole_side is the solder_short escape hatch.
    scope_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="per_component",
        server_default="per_component",
    )
    # detector_presets: list[str] of names from
    # data/defect_detector_mapping.yaml — never freeform. The M4 adapter
    # reads this column to build the graphflow subgraph per designator.
    detector_presets: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Preserved extra columns from the original BOM upload (manufacturer,
    # tolerance, supplier, etc.) — schemaless on purpose.
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    project: Mapped[Project] = relationship(back_populates="bom_items")


class ProposedPipelineRow(Base):
    """Versioned planner output. Latest version per project wins; we keep
    history so prompt-engineering regressions can be diffed later."""

    __tablename__ = "proposed_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    dag_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="proposed_pipelines")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "version", name="uq_proposed_pipelines_project_version"
        ),
    )


class AdaptRun(Base):
    """One row per `/api/projects/{id}/adapt` invocation. Records where
    the graphflow model dir was written so the operator can audit
    history without scanning the filesystem."""

    __tablename__ = "adapt_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pcb_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_dir: Mapped[str] = mapped_column(Text, nullable=False)
    inspected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="ok",
        server_default="ok",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="adapt_runs")
    train_runs: Mapped[list["TrainRun"]] = relationship(
        back_populates="adapt_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PreLabel(Base):
    """Phase 5.2 — latest pre-label set per (project_id, side).

    Pre-labels are emitted by the M5 Gemma-driven assistant; the M6 canvas
    fetches them and bakes the regions into the LSF task as `predictions[]`
    so the operator opens an annotated board on first visit.
    Latest-wins per side (UNIQUE constraint enforces single row); re-running
    the assistant replaces the row in-place via UPSERT in the route layer."""

    __tablename__ = "pre_labels"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    regions_json: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="pre_labels")

    __table_args__ = (
        UniqueConstraint("project_id", "side", name="uq_pre_labels_project_side"),
    )


class Label(Base):
    """Phase 6.2 — versioned LSF annotation per (project_id, side).

    Stores the raw LS-JSON `result[]` exactly as emitted by the canvas's
    onSubmitAnnotation callback. Version bumps on every save so prompt
    diffs and prior eval-set comparisons stay reproducible. Latest
    version per side is what M7 training reads."""

    __tablename__ = "labels"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ls_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="labels")

    __table_args__ = (
        UniqueConstraint(
            "project_id", "side", "version", name="uq_labels_project_side_version"
        ),
    )


class TrainRun(Base):
    """Phase 7.2 — one row per `/api/projects/{id}/training/start` call.

    The auto-inspect-service assigns a `service_job_id` synchronously and
    then streams progress events over SSE; this row tracks the lifecycle.
    `status` walks the standard machine pending → running → terminal
    (succeeded / failed / cancelled). Terminal metrics land in
    `metrics_json` (per-component F1 + mAP per the M9 eval contract).

    The `adapt_run_id` link makes the lineage reproducible: a TrainRun
    always knows the exact graphflow tree it was trained against.
    """

    __tablename__ = "train_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adapt_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("adapt_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="train_runs")
    adapt_run: Mapped[AdaptRun] = relationship(back_populates="train_runs")
