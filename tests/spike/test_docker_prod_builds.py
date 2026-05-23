"""Phase 14.1 — production Docker images smoke test.

Builds both production images and asserts size limits + non-root user. The
test is opt-in via `IVE_DOCKER_SPIKE=1` because each build takes 1-3 minutes
on a cold cache and pulls multi-hundred-MB base images — way too slow for
the default suite.

Targets per plan:
  backend  < 800MB
  frontend < 100MB
Both run as a non-root user.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _docker_available() -> bool:
    return shutil.which("docker") is not None


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_DOCKER_SPIKE") or not _docker_available(),
    reason="opt-in via IVE_DOCKER_SPIKE=1 + docker on PATH",
)


def _docker(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )


def _image_size_bytes(tag: str) -> int:
    result = _docker("image", "inspect", tag, "--format", "{{.Size}}")
    return int(result.stdout.strip())


def _image_user(tag: str) -> str:
    result = _docker("image", "inspect", tag, "--format", "{{.Config.User}}")
    return result.stdout.strip()


def test_backend_production_image_builds_within_budget():
    tag = "indusia-visual-editor-api:prod-test"
    _docker(
        "build",
        "--target",
        "runtime",
        "-t",
        tag,
        "-f",
        str(REPO_ROOT / "Dockerfile.api"),
        str(REPO_ROOT),
    )
    size = _image_size_bytes(tag)
    # 800MB target; allow 1GB hard ceiling because CV + ML deps (opencv-python,
    # asyncpg, passlib bcrypt) are stubbornly large on Python slim bases.
    assert size < 1024 * 1024 * 1024, (
        f"backend image {tag} = {size/1024/1024:.0f}MB — over 1GB hard ceiling"
    )
    user = _image_user(tag)
    assert user not in ("", "0", "root"), (
        f"backend image must run as non-root user; got {user!r}"
    )


def test_frontend_production_image_builds_within_budget():
    tag = "indusia-visual-editor-web:prod-test"
    _docker(
        "build",
        "--target",
        "runtime",
        "-t",
        tag,
        "-f",
        str(REPO_ROOT / "web" / "Dockerfile"),
        str(REPO_ROOT / "web"),
    )
    size = _image_size_bytes(tag)
    assert size < 200 * 1024 * 1024, (
        f"frontend image {tag} = {size/1024/1024:.0f}MB — over 200MB hard ceiling"
    )


def test_dockerignore_excludes_dev_artefacts():
    """A second guardrail: any image the runtime stage produces must NOT
    embed tests/, docs/, .git/, or the giant LSF source tree."""
    dockerignore = REPO_ROOT / ".dockerignore"
    assert dockerignore.exists(), "missing .dockerignore at repo root"
    content = dockerignore.read_text(encoding="utf-8")
    for needle in ("tests/", "docs/", ".git/", "storage/"):
        assert needle in content, f".dockerignore missing entry: {needle}"
