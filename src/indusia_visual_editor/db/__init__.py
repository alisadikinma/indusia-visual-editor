"""Database layer: SQLAlchemy 2.x async models + session factory.

Public surface:
- `Base` — declarative base class for all models
- `Project`, `Asset`, `BomItem` — Phase 1.1 models
- `ProjectStatus`, `AssetKind`, `InspectScope` — typed enums used by the models
- `get_engine()`, `get_sessionmaker()`, `get_session` — async engine + FastAPI dep
"""

from indusia_visual_editor.db.models import (
    Asset,
    AssetKind,
    Base,
    BomItem,
    InspectScope,
    Project,
    ProjectStatus,
)
from indusia_visual_editor.db.session import get_engine, get_session, get_sessionmaker

__all__ = [
    "Asset",
    "AssetKind",
    "Base",
    "BomItem",
    "InspectScope",
    "Project",
    "ProjectStatus",
    "get_engine",
    "get_session",
    "get_sessionmaker",
]
