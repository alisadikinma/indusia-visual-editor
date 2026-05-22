"""Phase 4.6 — POST/GET /api/projects/{id}/adapt route + persistence.

Happy path writes the model dir under a monkeypatched IVE_MODELS_ROOT
and persists an adapt_runs row. Error cases (no plan, all skipped)
return 422 envelope and persist NOTHING (no row, no dir).
"""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.config import get_config
from indusia_visual_editor.db.models import AdaptRun, ProposedPipelineRow
from indusia_visual_editor.main import app


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_models_root(tmp_path, monkeypatch):
    """Point IVE_MODELS_ROOT at tmp_path so each test gets a fresh dir."""
    monkeypatch.setenv("IVE_MODELS_ROOT", str(tmp_path))
    get_config.cache_clear() if hasattr(get_config, "cache_clear") else None
    yield tmp_path
    get_config.cache_clear() if hasattr(get_config, "cache_clear") else None


@pytest.fixture
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"adapt-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["id"])


async def _upload_bom(client: AsyncClient, project_id: uuid.UUID, designators: list[str]) -> None:
    rows = b"Designator,Value\n" + b"\n".join(
        f"{d},10k".encode() for d in designators
    )
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(rows), "text/csv")},
    )
    assert r.status_code == 201


async def _seed_plan(session: AsyncSession, project_id: uuid.UUID) -> None:
    dag = {"pcb_model": "NV80", "fiducial_strategy": "circle", "steps": []}
    session.add(ProposedPipelineRow(project_id=project_id, version=1, dag_json=dag))
    await session.commit()


def _annotation_body(rows: list[tuple[str, str, list[str]]]) -> dict:
    """rows: list of (designator, scope, criteria)."""
    result: list[dict] = []
    for designator, scope, criteria in rows:
        region_id = f"r-{designator}"
        result.append(
            {
                "id": region_id, "type": "rectanglelabels",
                "from_name": "component", "to_name": "image",
                "value": {"rectanglelabels": [designator]},
            }
        )
        result.append(
            {
                "id": region_id, "type": "choices",
                "from_name": "inspect_scope", "to_name": "image",
                "value": {"choices": [scope]},
            }
        )
        result.append(
            {
                "id": region_id, "type": "choices",
                "from_name": "scope_mode", "to_name": "image",
                "value": {"choices": ["per_component"]},
            }
        )
        if criteria:
            result.append(
                {
                    "id": region_id, "type": "choices",
                    "from_name": "defect_criteria", "to_name": "image",
                    "value": {"choices": criteria},
                }
            )
    return {"lsf_annotation": {"result": result}}


@pytest.mark.asyncio
async def test_post_adapt_writes_tree_and_persists_row(
    client: AsyncClient,
    query_session: AsyncSession,
    isolated_models_root: Path,
):
    pid = await _create_project(client, "happy")
    await _upload_bom(client, pid, ["R1", "C4"])
    await _seed_plan(query_session, pid)

    body = _annotation_body(
        [
            ("R1", "inspected", ["missing_component"]),
            ("C4", "skipped", []),
        ]
    )

    r = await client.post(f"/api/projects/{pid}/adapt", json=body)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["pcb_name"] == "NV80"
    assert data["inspected_count"] == 1
    assert data["status"] == "ok"

    pcb_dir = isolated_models_root / "NV80"
    assert pcb_dir.is_dir()
    assert (pcb_dir / "components" / "comp-R1.yaml").is_file()
    assert not (pcb_dir / "components" / "comp-C4.yaml").is_file()

    rows = (
        await query_session.execute(
            select(AdaptRun).where(AdaptRun.project_id == pid)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].pcb_name == "NV80"
    assert rows[0].inspected_count == 1


@pytest.mark.asyncio
async def test_post_adapt_422_when_no_plan(
    client: AsyncClient,
    query_session: AsyncSession,
    isolated_models_root: Path,
):
    pid = await _create_project(client, "noplan")
    body = _annotation_body([("R1", "inspected", ["missing_component"])])

    r = await client.post(f"/api/projects/{pid}/adapt", json=body)
    assert r.status_code == 422, r.text
    assert r.json()["status"] is False

    # No row, no dir
    rows = (
        await query_session.execute(
            select(AdaptRun).where(AdaptRun.project_id == pid)
        )
    ).scalars().all()
    assert rows == []
    assert list(isolated_models_root.iterdir()) == []


@pytest.mark.asyncio
async def test_post_adapt_422_when_all_skipped(
    client: AsyncClient,
    query_session: AsyncSession,
    isolated_models_root: Path,
):
    pid = await _create_project(client, "allskip")
    await _seed_plan(query_session, pid)
    body = _annotation_body(
        [
            ("R1", "skipped", []),
            ("C4", "skipped", []),
        ]
    )

    r = await client.post(f"/api/projects/{pid}/adapt", json=body)
    assert r.status_code == 422
    assert r.json()["status"] is False

    rows = (
        await query_session.execute(
            select(AdaptRun).where(AdaptRun.project_id == pid)
        )
    ).scalars().all()
    assert rows == []
    assert list(isolated_models_root.iterdir()) == []


@pytest.mark.asyncio
async def test_get_adapt_history_returns_rows_in_desc_created_order(
    client: AsyncClient,
    query_session: AsyncSession,
):
    pid = await _create_project(client, "history")
    await _seed_plan(query_session, pid)
    body = _annotation_body([("R1", "inspected", ["missing_component"])])

    for _ in range(2):
        r = await client.post(f"/api/projects/{pid}/adapt", json=body)
        assert r.status_code == 201

    r = await client.get(f"/api/projects/{pid}/adapt")
    assert r.status_code == 200
    history = r.json()["data"]
    assert len(history) == 2
    # Most recent first
    assert history[0]["created_at"] >= history[1]["created_at"]


@pytest.mark.asyncio
async def test_post_adapt_404_when_project_missing(client: AsyncClient):
    fake = uuid.uuid4()
    body = _annotation_body([("R1", "inspected", ["missing_component"])])
    r = await client.post(f"/api/projects/{fake}/adapt", json=body)
    assert r.status_code == 404
    assert r.json()["status"] is False
