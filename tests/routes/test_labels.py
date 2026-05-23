"""Phase 6.3 — GET task + POST submit label routes.

The labeling canvas (M6) is fed by GET /api/projects/{id}/labels/task — a
composed LSF task JSON with the golden image URL, the pre-label predictions
baked in, and an XML labeling config derived from the BOM designator list.

On submit, POST /api/projects/{id}/labels receives the raw LSF annotation
JSON, validates it via `LSAnnotation`, runs it through `derive_inspect_scope`,
propagates the per-region `inspect_scope` back to the matching bom_items
row, and persists the full annotation as a new version in the `labels` table.

Tests run against the real Postgres dev container; LSF itself is not
exercised here (that's Phase 6.5's Vitest suite).
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import BomItem, InspectScope, Label
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.llm import (
    reset_llm_client_factory,
    set_llm_client_factory,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


# A 1x1 PNG — small enough to embed verbatim; only used so the asset upload
# path can persist *something*. The route reads the asset to derive
# image_dims for the LSF task, so PNG-header parsing must handle this.
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class _FakeOllamaClient:
    """Reused for the pre-label setup step."""

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def generate(self, **_kwargs) -> str:
        return (
            '{"regions": ['
            '{"designator": "R1", "bbox": [0.10, 0.20, 0.05, 0.05], '
            '"confidence": 0.92, "side": "top"},'
            '{"designator": "C4", "bbox": [0.30, 0.40, 0.06, 0.06], '
            '"confidence": 0.88, "side": "top"}'
            "]}"
        )

    async def chat(self, **_kwargs) -> str:
        return ""

    async def aclose(self) -> None:
        pass


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def isolated_storage_root(tmp_path, monkeypatch):
    monkeypatch.setenv("IVE_STORAGE_ROOT", str(tmp_path))


@pytest.fixture
async def query_session():
    engine = create_async_engine(os.environ["IVE_DATABASE_URL"], future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture(autouse=True)
def fake_ollama():
    set_llm_client_factory(_FakeOllamaClient)
    yield
    reset_llm_client_factory()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"labels-{suffix}-{uuid.uuid4().hex[:8]}"
    r = await client.post("/api/projects", json={"name": slug, "slug": slug})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["id"])


async def _upload_bom(client: AsyncClient, project_id: uuid.UUID) -> None:
    csv = b"Designator,Value\nR1,10k\nC4,100uF\n"
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "bom"},
        files={"file": ("bom.csv", io.BytesIO(csv), "text/csv")},
    )
    assert r.status_code == 201, r.text


async def _upload_golden(
    client: AsyncClient, project_id: uuid.UUID, side: str = "top"
) -> None:
    # Mutate one byte per side so save_asset's (project_id, sha256) dedup
    # doesn't collapse top and bottom into one asset when the test reuses
    # the same canned PNG.
    payload = bytearray(PNG_1X1)
    if side == "bottom":
        payload[-1] ^= 0x01
    kind = f"golden_{side}"
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": kind},
        files={"file": (f"g_{side}.png", io.BytesIO(bytes(payload)), "image/png")},
    )
    assert r.status_code == 201, r.text


async def _seed_prelabel(client: AsyncClient, project_id: uuid.UUID, side: str) -> None:
    r = await client.post(
        f"/api/projects/{project_id}/llm/prelabel", params={"side": side}
    )
    assert r.status_code == 201, r.text


# ---------------- GET /labels/task ----------------


@pytest.mark.asyncio
async def test_get_task_returns_lsf_task_json_with_predictions(client: AsyncClient):
    pid = await _create_project(client, "task-happy")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")
    await _seed_prelabel(client, pid, "top")

    r = await client.get(
        f"/api/projects/{pid}/labels/task", params={"side": "top"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]

    # Required top-level pieces of an LSF task.
    assert "config" in data, "missing LSF XML config"
    assert "task" in data, "missing LSF task JSON"

    config_xml = data["config"]
    assert config_xml.startswith("<View>") and config_xml.endswith("</View>")
    assert '<Image name="image"' in config_xml
    assert '<RectangleLabels name="label"' in config_xml
    # Every BOM designator gets a <Label> entry.
    assert 'value="R1"' in config_xml
    assert 'value="C4"' in config_xml
    # Per-region choices for inspect_scope + scope_mode + defect_criteria.
    assert 'name="inspect_scope"' in config_xml
    assert 'name="scope_mode"' in config_xml
    assert 'name="defect_criteria"' in config_xml
    # The 9 canonical criteria must all be enumerated.
    for criterion in (
        "missing_component",
        "orientation",
        "polarity_flip",
        "connector_pin_bending",
        "missing_pin_connector",
        "lifted_pin",
        "wrong_value",
        "misalignment",
        "solder_short",
    ):
        assert f'value="{criterion}"' in config_xml, f"missing criterion {criterion}"

    task = data["task"]
    assert "data" in task and "image" in task["data"]
    # Image URL points back at the binary endpoint (relative path — the
    # frontend prepends API base before passing to LSF).
    assert task["data"]["image"].startswith(f"/api/projects/{pid}/assets/")
    assert task["data"]["image"].endswith("/binary")

    # Predictions baked in from the latest pre-label.
    assert "predictions" in task
    assert len(task["predictions"]) == 1
    pred = task["predictions"][0]
    assert "result" in pred
    assert len(pred["result"]) == 2  # R1 + C4
    first = pred["result"][0]
    assert first["type"] == "rectanglelabels"
    assert first["from_name"] == "label"
    assert first["to_name"] == "image"
    # bbox 0.10,0.20,0.05,0.05 normalized → 10,20,5,5 percentage.
    assert first["value"]["x"] == pytest.approx(10.0)
    assert first["value"]["y"] == pytest.approx(20.0)
    assert first["value"]["width"] == pytest.approx(5.0)
    assert first["value"]["height"] == pytest.approx(5.0)
    assert first["value"]["rectanglelabels"] == ["R1"]

    # annotations[] always present (even if empty) — LSF requires the array.
    assert "annotations" in task
    assert isinstance(task["annotations"], list)


@pytest.mark.asyncio
async def test_get_task_works_without_prelabel(client: AsyncClient):
    """A pre-label is optional — task still renders with empty predictions[]."""
    pid = await _create_project(client, "task-noprelabel")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    r = await client.get(
        f"/api/projects/{pid}/labels/task", params={"side": "top"}
    )
    assert r.status_code == 200, r.text
    task = r.json()["data"]["task"]
    assert task["predictions"] == []


@pytest.mark.asyncio
async def test_get_task_422_missing_golden(client: AsyncClient):
    pid = await _create_project(client, "task-nogold")
    await _upload_bom(client, pid)
    r = await client.get(
        f"/api/projects/{pid}/labels/task", params={"side": "top"}
    )
    assert r.status_code == 422
    assert "golden_top" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_task_422_no_bom(client: AsyncClient):
    pid = await _create_project(client, "task-nobom")
    await _upload_golden(client, pid, "top")
    r = await client.get(
        f"/api/projects/{pid}/labels/task", params={"side": "top"}
    )
    assert r.status_code == 422
    assert "bom" in r.json()["message"].lower()


@pytest.mark.asyncio
async def test_get_task_422_invalid_side(client: AsyncClient):
    pid = await _create_project(client, "task-badside")
    r = await client.get(
        f"/api/projects/{pid}/labels/task", params={"side": "diagonal"}
    )
    assert r.status_code == 422


# ---------------- POST /labels ----------------


def _annotation_with(designator: str, scope: str, criteria: list[str] | None = None) -> dict:
    """Build a minimal LS-JSON annotation result[] for one region."""
    region_id = uuid.uuid4().hex[:10]
    out = {
        "result": [
            {
                "id": region_id,
                "type": "rectanglelabels",
                "from_name": "label",
                "to_name": "image",
                "image_rotation": 0,
                "original_width": 100,
                "original_height": 100,
                "value": {
                    "x": 10.0,
                    "y": 20.0,
                    "width": 5.0,
                    "height": 5.0,
                    "rotation": 0,
                    "rectanglelabels": [designator],
                },
            },
            {
                "id": region_id,
                "type": "choices",
                "from_name": "inspect_scope",
                "to_name": "image",
                "value": {"choices": [scope]},
            },
            {
                "id": region_id,
                "type": "choices",
                "from_name": "scope_mode",
                "to_name": "image",
                "value": {"choices": ["per_component"]},
            },
        ]
    }
    if criteria and scope == "inspected":
        out["result"].append(
            {
                "id": region_id,
                "type": "choices",
                "from_name": "defect_criteria",
                "to_name": "image",
                "value": {"choices": criteria},
            }
        )
    return out


@pytest.mark.asyncio
async def test_post_labels_persists_version_and_updates_bom_inspect_scope(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "submit-happy")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    ann = _annotation_with("R1", "inspected", ["missing_component"])
    # Add a second region for C4 marked skipped.
    skip = _annotation_with("C4", "skipped")
    ann["result"].extend(skip["result"])

    r = await client.post(
        f"/api/projects/{pid}/labels",
        params={"side": "top"},
        json={"ls_json": ann},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] is True
    assert body["data"]["version"] == 1
    assert body["data"]["side"] == "top"

    # Label row persisted with full ls_json.
    label_rows = (
        await query_session.execute(select(Label).where(Label.project_id == pid))
    ).scalars().all()
    assert len(label_rows) == 1
    assert label_rows[0].version == 1
    assert len(label_rows[0].ls_json["result"]) == len(ann["result"])

    # bom_items updated: R1 → inspected, C4 → skipped.
    boms = (
        await query_session.execute(
            select(BomItem).where(BomItem.project_id == pid).order_by(BomItem.designator)
        )
    ).scalars().all()
    by_des = {b.designator: b for b in boms}
    assert by_des["C4"].inspect_scope == InspectScope.SKIPPED
    assert by_des["R1"].inspect_scope == InspectScope.INSPECTED


@pytest.mark.asyncio
async def test_post_labels_version_increments_on_resubmit(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "submit-versioning")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    for expected_version in (1, 2, 3):
        r = await client.post(
            f"/api/projects/{pid}/labels",
            params={"side": "top"},
            json={"ls_json": _annotation_with("R1", "inspected", ["missing_component"])},
        )
        assert r.status_code == 201, r.text
        assert r.json()["data"]["version"] == expected_version

    rows = (
        await query_session.execute(
            select(Label).where(Label.project_id == pid).order_by(Label.version)
        )
    ).scalars().all()
    assert [r.version for r in rows] == [1, 2, 3]


@pytest.mark.asyncio
async def test_post_labels_top_and_bottom_version_independently(
    client: AsyncClient, query_session: AsyncSession
):
    """Versions count per (project, side); top v1 and bottom v1 coexist."""
    pid = await _create_project(client, "submit-bothsides")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")
    await _upload_golden(client, pid, "bottom")

    r_top = await client.post(
        f"/api/projects/{pid}/labels",
        params={"side": "top"},
        json={"ls_json": _annotation_with("R1", "inspected", ["missing_component"])},
    )
    r_bot = await client.post(
        f"/api/projects/{pid}/labels",
        params={"side": "bottom"},
        json={"ls_json": _annotation_with("C4", "skipped")},
    )
    assert r_top.json()["data"]["version"] == 1
    assert r_bot.json()["data"]["version"] == 1


@pytest.mark.asyncio
async def test_post_labels_422_on_unknown_criterion(client: AsyncClient):
    pid = await _create_project(client, "submit-badcrit")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    ann = _annotation_with("R1", "inspected", ["not_a_real_criterion"])
    r = await client.post(
        f"/api/projects/{pid}/labels",
        params={"side": "top"},
        json={"ls_json": ann},
    )
    assert r.status_code == 422, r.text
    assert "not_a_real_criterion" in r.json()["message"]


@pytest.mark.asyncio
async def test_post_labels_422_on_malformed_ls_json(client: AsyncClient):
    pid = await _create_project(client, "submit-badjson")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    r = await client.post(
        f"/api/projects/{pid}/labels",
        params={"side": "top"},
        json={"ls_json": {"notresult": "broken"}},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_post_labels_422_invalid_side(client: AsyncClient):
    pid = await _create_project(client, "submit-badside")
    r = await client.post(
        f"/api/projects/{pid}/labels",
        params={"side": "left"},
        json={"ls_json": _annotation_with("R1", "skipped")},
    )
    assert r.status_code == 422
