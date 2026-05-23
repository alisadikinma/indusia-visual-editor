"""Response schema for the M9 eval surface (Phase 9.1)."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class EvalRead(BaseModel):
    """Shape returned by `GET /api/training/{run_id}/eval`.

    `metrics` is whatever `train_runs.metrics_json` was populated with by
    the M7 SSE relay on the terminal `succeeded` event (per-component F1 +
    mAP). `predictions` is the list fetched live from auto-inspect-service.
    `prev_metrics` is the second-most-recent succeeded run's metrics for
    the same project, used by the Vue layer to render delta indicators.
    """

    run_id: uuid.UUID
    metrics: dict[str, Any]
    predictions: list[dict[str, Any]]
    prev_metrics: dict[str, Any] | None
