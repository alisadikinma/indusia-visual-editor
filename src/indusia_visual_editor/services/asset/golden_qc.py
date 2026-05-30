"""Golden-sample image QC (T6 / gap G4).

A golden sample feeds the anomaly-on-good model and is the visual reference
the operator labels against. A blurry or badly-exposed golden poisons both.
This module runs two objective, fast checks on the uploaded image BEFORE it
is trusted:

  - sharpness  — variance of the Laplacian (defocus / motion blur detector)
  - exposure   — mean luminance band + clipped-pixel fractions (too dark /
                 blown-out highlights)

The thresholds below are defensible DEFAULTS, not absolute standards — there
is no universal blur cutoff (it depends on magnification, content, and
lighting; see ai-visual-inspection-expert §7 "lighting before model"). They
are tuned for the relative call "is this golden good enough to trust?" and
are meant to be recalibrated per line. The verdict is an operator nudge, not
one of the two HITL gates.

`assess_golden_qc` returns the raw metrics alongside the verdict so the UI can
show the numbers, never just a opaque pass/fail.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

# --- default thresholds (configurable / recalibrate per line) ---
SHARPNESS_FAIL = 60.0   # Laplacian variance below this → clearly blurry
SHARPNESS_WARN = 120.0  # below this → soft-focus, review

LUMA_OK_LOW = 40.0      # healthy mean-luminance band (0–255)
LUMA_OK_HIGH = 215.0
LUMA_FAIL_LOW = 25.0    # outside this → fail (too dark / too bright)
LUMA_FAIL_HIGH = 230.0

DARK_PIXEL = 16         # pixel value at/below = crushed shadow
BRIGHT_PIXEL = 239      # pixel value at/above = blown highlight
CLIP_WARN = 0.10        # >10% clipped → review
CLIP_FAIL = 0.25        # >25% clipped → fail


class GoldenQcError(ValueError):
    """Raised when the bytes cannot be decoded as an image."""


def _decode_gray(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        raise GoldenQcError("image bytes could not be decoded")
    return img


def assess_golden_qc(image_bytes: bytes) -> dict[str, Any]:
    """Score a golden-sample image. Returns metrics + verdict + reasons.

    verdict ∈ {"ok", "warn", "fail"}; reasons is a list of short codes the UI
    maps to operator-facing copy. Raises GoldenQcError on undecodable bytes."""
    gray = _decode_gray(image_bytes)

    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_luma = float(gray.mean())
    total = float(gray.size)
    clipped_dark = float((gray <= DARK_PIXEL).sum()) / total
    clipped_bright = float((gray >= BRIGHT_PIXEL).sum()) / total

    reasons: list[str] = []
    verdict = "ok"

    def _demote(level: str) -> None:
        nonlocal verdict
        order = {"ok": 0, "warn": 1, "fail": 2}
        if order[level] > order[verdict]:
            verdict = level

    # sharpness
    if sharpness < SHARPNESS_FAIL:
        reasons.append("blur_fail")
        _demote("fail")
    elif sharpness < SHARPNESS_WARN:
        reasons.append("blur_warn")
        _demote("warn")

    # exposure — mean luminance band
    if mean_luma < LUMA_FAIL_LOW or mean_luma > LUMA_FAIL_HIGH:
        reasons.append("exposure_fail")
        _demote("fail")
    elif mean_luma < LUMA_OK_LOW or mean_luma > LUMA_OK_HIGH:
        reasons.append("exposure_warn")
        _demote("warn")

    # exposure — clipping
    if clipped_dark >= CLIP_FAIL:
        reasons.append("dark_clip_fail")
        _demote("fail")
    elif clipped_dark >= CLIP_WARN:
        reasons.append("dark_clip_warn")
        _demote("warn")
    if clipped_bright >= CLIP_FAIL:
        reasons.append("bright_clip_fail")
        _demote("fail")
    elif clipped_bright >= CLIP_WARN:
        reasons.append("bright_clip_warn")
        _demote("warn")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "sharpness": round(sharpness, 2),
        "mean_luminance": round(mean_luma, 2),
        "clipped_dark": round(clipped_dark, 4),
        "clipped_bright": round(clipped_bright, 4),
    }
