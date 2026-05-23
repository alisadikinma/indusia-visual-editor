"""Phase 8.3 supporting route — POST /api/projects/{id}/training/suggest-hyperparams.

Composes the M8.1 dataset stats + the M8.2 hyperparams orchestrator so the
Gate-1 view can render a "Mulai Training" preview in one fetch. Reuses the
existing fake-Ollama factory seam.

Tests:
1. Happy path with a labeled side returns a Hyperparameters envelope.
2. 404 when the project has no label for that side yet (gate is closed).
3. 422 on invalid side.
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

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
    """Returns a deterministic prelabel response and a deterministic
    hyperparams response — the route can't tell which call is which
    because we identify by the format/schema being sent. We just always
    return whatever was last queued via the class attribute."""

    prelabel_response = (
        '{"regions": ['
        '{"designator": "R1", "bbox": [0.10, 0.20, 0.05, 0.05], '
        '"confidence": 0.92, "side": "top"},'
        '{"designator": "C4", "bbox": [0.30, 0.40, 0.06, 0.06], '
        '"confidence": 0.88, "side": "top"}'
        "]}"
    )
    hyperparams_response = (
        '{"epochs": 40, "batch_size": 16, '
        '"augmentation_intensity": "medium", '
        '"notes": "Distribusi label seimbang; aug medium cukup."}'
    )

    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url
        self.timeout = timeout

    async def generate(self, **kwargs) -> str:
        schema = kwargs.get("format")
        # Hyperparameters schema has an `augmentation_intensity` property;
        # the pre-label schema does not. That's enough to disambiguate.
        if isinstance(schema, dict) and "augmentation_intensity" in str(schema):
            return type(self).hyperparams_response
        return type(self).prelabel_response

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


@pytest.fixture(autouse=True)
def fake_ollama():
    set_llm_client_factory(_FakeOllamaClient)
    yield
    reset_llm_client_factory()


async def _create_project(client: AsyncClient, suffix: str) -> uuid.UUID:
    slug = f"hyp-{suffix}-{uuid.uuid4().hex[:8]}"
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


async def _upload_golden(client: AsyncClient, project_id: uuid.UUID) -> None:
    r = await client.post(
        f"/api/projects/{project_id}/assets",
        params={"kind": "golden_top"},
        files={"file": ("g.png", io.BytesIO(PNG_1X1), "image/png")},
    )
    assert r.status_code == 201, r.text


async def _seed_prelabel(client: AsyncClient, project_id: uuid.UUID) -> None:
    r = await client.post(
        f"/api/projects/{project_id}/llm/prelabel", params={"side": "top"}
    )
    assert r.status_code == 201, r.text


async def _submit_label(client: AsyncClient, project_id: uuid.UUID) -> None:
    region_id = uuid.uuid4().hex[:10]
    ann = {
        "result": [
            {
                "id": region_id,
                "type": "rectanglelabels",
                "from_name": "label",
                "to_name": "image",
                "value": {
                    "x": 10.0,
                    "y": 20.0,
                    "width": 5.0,
                    "height": 5.0,
                    "rotation": 0,
                    "rectanglelabels": ["R1"],
                },
            },
            {
                "id": region_id,
                "type": "choices",
                "from_name": "inspect_scope",
                "to_name": "image",
                "value": {"choices": ["inspected"]},
            },
            {
                "id": region_id,
                "type": "choices",
                "from_name": "scope_mode",
                "to_name": "image",
                "value": {"choices": ["per_component"]},
            },
            {
                "id": region_id,
                "type": "choices",
                "from_name": "defect_criteria",
                "to_name": "image",
                "value": {"choices": ["missing_component"]},
            },
        ]
    }
    r = await client.post(
        f"/api/projects/{project_id}/labels",
        params={"side": "top"},
        json={"ls_json": ann},
    )
    assert r.status_code == 201, r.text


# ---------------- happy path ----------------


@pytest.mark.asyncio
async def test_suggest_hyperparams_happy_path(client: AsyncClient):
    pid = await _create_project(client, "happy")
    await _upload_bom(client, pid)
    await _upload_golden(client, pid)
    await _seed_prelabel(client, pid)
    await _submit_label(client, pid)

    r = await client.post(
        f"/api/projects/{pid}/training/suggest-hyperparams",
        params={"side": "top"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] is True
    data = body["data"]

    # The hyperparams envelope.
    hp = data["hyperparameters"]
    assert hp["epochs"] == 40
    assert hp["batch_size"] == 16
    assert hp["augmentation_intensity"] == "medium"
    assert hp["notes"]

    # The stats it was based on are echoed so the UI can show "what we
    # asked Gemma" without a second round-trip.
    stats = data["stats"]
    assert stats["total"] == 1
    assert stats["inspected"] == 1


# ---------------- 404 no label ----------------


@pytest.mark.asyncio
async def test_suggest_hyperparams_404_when_no_label(client: AsyncClient):
    pid = await _create_project(client, "nolabel")
    await _upload_bom(client, pid)
    r = await client.post(
        f"/api/projects/{pid}/training/suggest-hyperparams",
        params={"side": "top"},
    )
    assert r.status_code == 404
    assert "label" in r.json()["message"].lower()


# ---------------- 422 invalid side ----------------


@pytest.mark.asyncio
async def test_suggest_hyperparams_422_invalid_side(client: AsyncClient):
    pid = await _create_project(client, "badside")
    r = await client.post(
        f"/api/projects/{pid}/training/suggest-hyperparams",
        params={"side": "diagonal"},
    )
    assert r.status_code == 422
