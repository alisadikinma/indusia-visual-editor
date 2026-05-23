"""Phase 8.1 — GET /api/projects/{id}/dataset/stats route.

Gate-1 dataset stats: reads the latest Label row for a given side, walks the
LS-JSON via `derive_inspect_scope`, joins back to `bom_items` for the
MI-likely / SMT split, and returns the counts the operator sees on the
"Mulai Training" approval panel.

Tests run against the real Postgres dev container; LSF itself is not
exercised here. Pre-label is seeded via the existing fake-Ollama route so
the labels POST has predictions to derive from.
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from indusia_visual_editor.db.models import BomItem
from indusia_visual_editor.main import app
from indusia_visual_editor.routes.llm import (
    reset_llm_client_factory,
    set_llm_client_factory,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DATABASE_URL"),
    reason="IVE_DATABASE_URL not set; start docker-compose.dev.yml postgres first.",
)


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


class _FakeOllamaClient:
    """Reused for the pre-label setup step — emits two regions (R1, C4)."""

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
    slug = f"stats-{suffix}-{uuid.uuid4().hex[:8]}"
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
    payload = bytearray(PNG_1X1)
    if side == "bottom":
        payload[-1] ^= 0x01
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": f"golden_{side}"},
        files={"file": (f"g_{side}.png", io.BytesIO(bytes(payload)), "image/png")},
    )
    assert r.status_code == 201, r.text


async def _seed_prelabel(
    client: AsyncClient, project_id: uuid.UUID, side: str
) -> None:
    r = await client.post(
        f"/api/projects/{project_id}/llm/prelabel", params={"side": side}
    )
    assert r.status_code == 201, r.text


def _annotation_for(
    designator: str, scope: str, criteria: list[str] | None = None
) -> dict:
    region_id = uuid.uuid4().hex[:10]
    out: dict = {
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


async def _submit_label(
    client: AsyncClient,
    project_id: uuid.UUID,
    side: str,
    annotation: dict,
) -> None:
    r = await client.post(
        f"/api/projects/{project_id}/labels",
        params={"side": side},
        json={"ls_json": annotation},
    )
    assert r.status_code == 201, r.text


# ---------------- happy path ----------------


@pytest.mark.asyncio
async def test_get_dataset_stats_returns_counts_per_criterion(
    client: AsyncClient, query_session: AsyncSession
):
    pid = await _create_project(client, "happy")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")
    await _seed_prelabel(client, pid, "top")

    # Force one row's mi_likely to True so the MI/SMT split shows non-zero
    # on both sides. The BOM parser leaves mi_likely=None unless the
    # heuristic fires; we set it explicitly so the test is deterministic.
    await query_session.execute(
        update(BomItem)
        .where(BomItem.project_id == pid, BomItem.designator == "R1")
        .values(mi_likely=True)
    )
    await query_session.execute(
        update(BomItem)
        .where(BomItem.project_id == pid, BomItem.designator == "C4")
        .values(mi_likely=False)
    )
    await query_session.commit()

    # Annotation: R1 inspected for missing_component + wrong_value,
    # C4 skipped. So stats should show 1 inspected, 1 skipped, 2 total.
    annotation = {
        "result": (
            _annotation_for(
                "R1", "inspected", ["missing_component", "wrong_value"]
            )["result"]
            + _annotation_for("C4", "skipped")["result"]
        )
    }
    await _submit_label(client, pid, "top", annotation)

    r = await client.get(
        f"/api/projects/{pid}/dataset/stats", params={"side": "top"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]

    assert data["side"] == "top"
    assert data["total"] == 2
    assert data["inspected"] == 1
    assert data["skipped"] == 1

    # Defect-criterion counts: only inspected regions contribute.
    per_crit = data["per_criterion"]
    assert per_crit["missing_component"] == 1
    assert per_crit["wrong_value"] == 1
    # Other criteria still listed (count 0) so the UI can render a stable grid.
    assert per_crit["solder_short"] == 0
    assert per_crit["polarity_flip"] == 0

    # MI/SMT split — both rows present in bom_items, so 1 MI + 1 SMT.
    assert data["mi_count"] == 1
    assert data["smt_count"] == 1

    # Designator coverage — both designators show up under their scope.
    designators = {item["designator"]: item for item in data["designators"]}
    assert designators["R1"]["inspect_scope"] == "inspected"
    assert designators["R1"]["defect_criteria"] == [
        "missing_component",
        "wrong_value",
    ]
    assert designators["C4"]["inspect_scope"] == "skipped"
    assert designators["C4"]["defect_criteria"] == []


# ---------------- 404 no label ----------------


@pytest.mark.asyncio
async def test_get_dataset_stats_404_when_no_label(client: AsyncClient):
    pid = await _create_project(client, "nolabel")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")

    r = await client.get(
        f"/api/projects/{pid}/dataset/stats", params={"side": "top"}
    )
    assert r.status_code == 404
    assert "label" in r.json()["message"].lower()


# ---------------- multi-side independence ----------------


@pytest.mark.asyncio
async def test_get_dataset_stats_top_and_bottom_are_independent(
    client: AsyncClient,
):
    pid = await _create_project(client, "twoside")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid, "top")
    await _upload_golden(client, pid, "bottom")
    await _seed_prelabel(client, pid, "top")
    await _seed_prelabel(client, pid, "bottom")

    # Top: R1 inspected, C4 inspected.
    top_ann = {
        "result": (
            _annotation_for("R1", "inspected", ["missing_component"])["result"]
            + _annotation_for("C4", "inspected", ["orientation"])["result"]
        )
    }
    await _submit_label(client, pid, "top", top_ann)

    # Bottom: only C4 inspected, R1 skipped.
    bot_ann = {
        "result": (
            _annotation_for("R1", "skipped")["result"]
            + _annotation_for("C4", "inspected", ["wrong_value"])["result"]
        )
    }
    await _submit_label(client, pid, "bottom", bot_ann)

    r_top = await client.get(
        f"/api/projects/{pid}/dataset/stats", params={"side": "top"}
    )
    r_bot = await client.get(
        f"/api/projects/{pid}/dataset/stats", params={"side": "bottom"}
    )

    assert r_top.status_code == 200
    assert r_bot.status_code == 200

    top_data = r_top.json()["data"]
    bot_data = r_bot.json()["data"]

    assert top_data["inspected"] == 2
    assert top_data["skipped"] == 0
    assert top_data["per_criterion"]["missing_component"] == 1
    assert top_data["per_criterion"]["orientation"] == 1

    assert bot_data["inspected"] == 1
    assert bot_data["skipped"] == 1
    assert bot_data["per_criterion"]["wrong_value"] == 1
    assert bot_data["per_criterion"]["missing_component"] == 0


# ---------------- 422 invalid side ----------------


@pytest.mark.asyncio
async def test_get_dataset_stats_422_invalid_side(client: AsyncClient):
    pid = await _create_project(client, "badside")
    r = await client.get(
        f"/api/projects/{pid}/dataset/stats", params={"side": "diagonal"}
    )
    assert r.status_code == 422
