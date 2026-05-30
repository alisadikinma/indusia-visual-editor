"""Registration pre-flight tests (T7 / gap G2).

Relative, pixel-domain checks only — NOT absolute µm registration (that needs
a calibration board + telecentric optics; see ai-visual-inspection-expert §7
and the honest-limit note in the module). Validates ORB feature-detectability
per golden + pairwise alignment residual when ≥2 samples are given.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from indusia_visual_editor.services.asset.registration import (
    RegistrationError,
    assess_registration,
)


def _encode(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def _textured() -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.integers(0, 255, size=(256, 256, 3), dtype=np.uint8)


def test_textured_golden_has_features_ok() -> None:
    res = assess_registration([_encode(_textured())])
    assert res["per_image"][0]["keypoints"] > 80
    assert res["verdict"] == "ok"
    assert res["pairwise_residual_px"] is None  # only one image


def test_flat_golden_lacks_features_fails() -> None:
    flat = np.full((256, 256, 3), 128, dtype=np.uint8)
    res = assess_registration([_encode(flat)])
    assert res["verdict"] == "fail"
    assert any("feature" in r for r in res["reasons"])


def test_pairwise_residual_recovers_known_shift() -> None:
    base = _textured()
    shifted = np.roll(base, 8, axis=1)  # shift 8 px in x
    res = assess_registration([_encode(base), _encode(shifted)])
    assert res["pairwise_residual_px"] is not None
    assert res["pairwise_residual_px"] == pytest.approx(8.0, abs=2.0)


def test_undecodable_raises() -> None:
    with pytest.raises(RegistrationError):
        assess_registration([b"nope"])
