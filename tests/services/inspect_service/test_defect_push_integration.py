"""I-1: opt-in end-to-end push against a LIVE auto-inspect-service (T1).

Skipped unless both:
  - IVE_INSPECT_SERVICE_INTEGRATION=1
  - IVE_DEFECT_PUSH_MODEL=<a model name that exists on the live service>

Run with a service started via `ais run` (port from IVE_INSPECT_SERVICE_URL).
Mirrors the existing opt-in pattern (test_training_client health check) so the
default unit suite never reaches out to the network.
"""

from __future__ import annotations

import os

import pytest

from indusia_visual_editor.config import get_config
from indusia_visual_editor.services.inspect_service.training_client import (
    TrainingClient,
)

pytestmark = pytest.mark.skipif(
    not (os.environ.get("IVE_INSPECT_SERVICE_INTEGRATION") and os.environ.get("IVE_DEFECT_PUSH_MODEL")),
    reason="set IVE_INSPECT_SERVICE_INTEGRATION=1 + IVE_DEFECT_PUSH_MODEL=<model> with a live auto-inspect-service",
)

# 1x1 PNG (smallest decodable image).
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6300010000000500010d0a2db40000000049454e44ae426082"
)


@pytest.mark.asyncio
async def test_push_supervised_then_anomaly_round_trip():
    cfg = get_config()
    model = os.environ["IVE_DEFECT_PUSH_MODEL"]
    client = TrainingClient(
        base_url=cfg.inspect_service_url, timeout=cfg.inspect_service_timeout
    )
    try:
        sup = await client.push_defect_example(
            model,
            criterion="missing_component",
            component="R1",
            source_id="ive-e2e-sup",
            image_data=_PNG,
        )
        assert sup["track"] == "supervised"
        assert sup["written"] is True

        anom = await client.push_defect_example(
            model,
            criterion="lifted_pin",
            component="J5",
            source_id="ive-e2e-anom",
            image_data=_PNG,
        )
        assert anom["track"] == "anomaly"
        assert anom["honest_limit"] is True

        ocr = await client.push_defect_example(
            model,
            criterion="wrong_value",
            component="U1",
            source_id="ive-e2e-ocr",
            image_data=_PNG,
        )
        assert ocr["track"] == "ocr_out_of_band"
        assert ocr["written"] is False
    finally:
        await client.aclose()
