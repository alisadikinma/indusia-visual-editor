"""Registration pre-flight for golden samples (T7 / gap G2).

Runtime inspection aligns each incoming board to the golden via fiducials
before any detector runs; if that alignment is shaky, every downstream call
inherits the error (ai-visual-inspection-expert §7: "false-call RCA order —
fiducial contrast first"). This module runs a cheap pre-flight on the golden
sample(s) BEFORE training/inspection is trusted.

HONEST LIMIT: absolute ±5 µm registration needs a calibration board and
telecentric optics — impossible from a web-uploaded JPEG. So this check is
RELATIVE and in the PIXEL domain only:

  1. feature-detectability — ORB keypoint count per image. Too few keypoints
     (low texture / blur / glare) means runtime fiducial/feature registration
     will be unreliable.
  2. pairwise consistency — when ≥2 golden samples of a side are given, the
     ORB-estimated translation/rotation residual between them (in pixels). A
     large residual means the captures are framed inconsistently.

The verdict is an operator nudge, not one of the two HITL gates.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np

# --- default thresholds (configurable / recalibrate per line) ---
MIN_KEYPOINTS_FAIL = 30   # below this → registration not viable
MIN_KEYPOINTS_WARN = 80   # below this → review (sparse features)
MIN_GOOD_MATCHES = 12     # need at least this many to estimate a transform
RESIDUAL_WARN_PX = 15.0   # pairwise offset above this → review
RESIDUAL_FAIL_PX = 40.0   # pairwise offset above this → fail

_ORB_FEATURES = 600


class RegistrationError(ValueError):
    """Raised when an input cannot be decoded as an image."""


def _decode_gray(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None or img.size == 0:
        raise RegistrationError("image bytes could not be decoded")
    return img


def _pairwise_residual_px(
    a_gray: np.ndarray, b_gray: np.ndarray
) -> float | None:
    """Estimate the translation residual (px) between two images via ORB.

    Returns None when too few robust matches exist to estimate a transform."""
    orb = cv2.ORB_create(nfeatures=_ORB_FEATURES)
    kp_a, des_a = orb.detectAndCompute(a_gray, None)
    kp_b, des_b = orb.detectAndCompute(b_gray, None)
    if des_a is None or des_b is None:
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(matcher.match(des_a, des_b), key=lambda m: m.distance)
    if len(matches) < MIN_GOOD_MATCHES:
        return None

    good = matches[: max(MIN_GOOD_MATCHES, len(matches) // 2)]
    src = np.float32([kp_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    matrix, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC)
    if matrix is None:
        return None
    tx, ty = float(matrix[0, 2]), float(matrix[1, 2])
    return round(math.hypot(tx, ty), 2)


def assess_registration(images: list[bytes]) -> dict[str, Any]:
    """Pre-flight the golden sample(s) for a side. Returns per-image feature
    counts + pairwise residual + verdict. Raises RegistrationError on
    undecodable bytes."""
    if not images:
        raise RegistrationError("no images supplied")

    grays = [_decode_gray(b) for b in images]
    orb = cv2.ORB_create(nfeatures=_ORB_FEATURES)

    per_image: list[dict[str, Any]] = []
    verdict = "ok"
    reasons: list[str] = []

    def _demote(level: str) -> None:
        nonlocal verdict
        order = {"ok": 0, "warn": 1, "fail": 2}
        if order[level] > order[verdict]:
            verdict = level

    for gray in grays:
        kps = orb.detect(gray, None)
        count = len(kps)
        ok = count >= MIN_KEYPOINTS_FAIL
        per_image.append({"keypoints": count, "ok": ok})
        if count < MIN_KEYPOINTS_FAIL:
            reasons.append("insufficient_features")
            _demote("fail")
        elif count < MIN_KEYPOINTS_WARN:
            reasons.append("sparse_features")
            _demote("warn")

    residual: float | None = None
    if len(grays) >= 2:
        residual = _pairwise_residual_px(grays[0], grays[1])
        if residual is None:
            reasons.append("unmatched_samples")
            _demote("warn")
        elif residual >= RESIDUAL_FAIL_PX:
            reasons.append("misaligned_fail")
            _demote("fail")
        elif residual >= RESIDUAL_WARN_PX:
            reasons.append("misaligned_warn")
            _demote("warn")

    # de-dup reasons preserving order
    seen: set[str] = set()
    reasons = [r for r in reasons if not (r in seen or seen.add(r))]

    return {
        "verdict": verdict,
        "reasons": reasons,
        "per_image": per_image,
        "pairwise_residual_px": residual,
        "sample_count": len(grays),
    }
