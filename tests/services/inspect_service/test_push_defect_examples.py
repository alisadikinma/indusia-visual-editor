"""V-2: push_defect_examples reads promoted examples + POSTs each to the service,
aggregating a report. DB-gated (real defect_examples rows)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import DefectExample, Project
from indusia_visual_editor.services.inspect_service.defect_push import (
    push_defect_examples,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


class _FakeClient:
    """Captures push calls; honest_limit echoes back for height-defect criteria."""

    def __init__(self):
        self.calls: list[dict] = []

    async def push_defect_example(self, model_name, *, criterion, component, source_id, image_data, bbox=None):
        self.calls.append({"criterion": criterion, "component": component, "source_id": source_id})
        honest = criterion in {"connector_pin_bending", "lifted_pin"}
        return {"track": "anomaly" if honest else "supervised", "honest_limit": honest, "written": True}


@pytest.fixture
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _project(session) -> uuid.UUID:
    pid = uuid.uuid4()
    session.add(Project(id=pid, name=f"P {pid.hex[:6]}", slug=f"p-{pid.hex[:8]}", status="drafting"))
    await session.commit()
    return pid


def _add_example(session, project_id, criterion, roi_path, designator="R1"):
    session.add(
        DefectExample(
            id=uuid.uuid4(),
            project_id=project_id,
            defect_criterion=criterion,
            roi_path=roi_path,
            roi_sha256="a" * 64,
            designator=designator,
        )
    )


@pytest.mark.asyncio
async def test_push_aggregates_report(query_session, tmp_path):
    pid = await _project(query_session)
    storage = tmp_path
    # 1 supervised (crop present), 1 anomaly height-defect (crop present),
    # 1 ocr (skipped, no POST), 1 supervised with a MISSING crop file.
    (storage / "crops").mkdir()
    for name in ("sup.png", "anom.png"):
        (storage / "crops" / name).write_bytes(b"\x89PNG\r\n")
    _add_example(query_session, pid, "missing_component", "crops/sup.png")
    _add_example(query_session, pid, "lifted_pin", "crops/anom.png", designator="J5")
    _add_example(query_session, pid, "wrong_value", "crops/whatever.png", designator="U1")
    _add_example(query_session, pid, "solder_short", "crops/gone.png")
    await query_session.commit()

    client = _FakeClient()
    report = await push_defect_examples(
        query_session, pid, client=client, model_name="pcb_1", storage_root=Path(storage)
    )

    assert report["total"] == 4
    assert report["pushed"] == 2  # supervised+anomaly with present crops
    assert report["skipped_ocr"] == 1  # wrong_value, never POSTed
    assert report["missing_crop"] == 1  # solder_short crop file absent
    assert report["needs_real_data"] == 1  # lifted_pin honest_limit
    assert report["by_track"]["supervised"] == 2
    assert report["by_track"]["anomaly"] == 1
    assert report["by_track"]["ocr_out_of_band"] == 1
    # ocr criterion was never sent to the service
    assert all(c["criterion"] != "wrong_value" for c in client.calls)
    assert len(client.calls) == 2
