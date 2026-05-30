"""Golden-sample QC tests (T6 / G4).

Pure image-quality checks — no DB. Validates the sharpness (Laplacian
variance) + exposure (luminance band + clipping) heuristics that gate a
golden sample before it pollutes the anomaly-on-good model.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from indusia_visual_editor.services.asset.golden_qc import (
    GoldenQcError,
    assess_golden_qc,
)


def _encode(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _sharp_well_exposed() -> bytes:
    # Mid-grey field with a high-contrast checkerboard → high Laplacian var,
    # mean luminance in the healthy band, no clipping.
    img = np.full((256, 256, 3), 128, dtype=np.uint8)
    img[::8, :] = 30
    img[:, ::8] = 220
    return _encode(img)


def _blurry() -> bytes:
    base = np.full((256, 256, 3), 128, dtype=np.uint8)
    base[::8, :] = 30
    base[:, ::8] = 220
    blurred = cv2.GaussianBlur(base, (31, 31), 0)
    return _encode(blurred)


def _too_dark() -> bytes:
    img = np.full((256, 256, 3), 6, dtype=np.uint8)
    return _encode(img)


def test_sharp_well_exposed_passes() -> None:
    qc = assess_golden_qc(_sharp_well_exposed())
    assert qc["verdict"] == "ok"
    assert qc["sharpness"] > 0
    assert 40 <= qc["mean_luminance"] <= 215


def test_blurry_image_is_flagged() -> None:
    qc = assess_golden_qc(_blurry())
    assert qc["verdict"] in {"warn", "fail"}
    assert any("blur" in r or "sharp" in r for r in qc["reasons"])


def test_too_dark_fails_exposure() -> None:
    qc = assess_golden_qc(_too_dark())
    assert qc["verdict"] == "fail"
    assert any("dark" in r or "expos" in r for r in qc["reasons"])


def test_undecodable_bytes_raise() -> None:
    with pytest.raises(GoldenQcError):
        assess_golden_qc(b"not-an-image")
