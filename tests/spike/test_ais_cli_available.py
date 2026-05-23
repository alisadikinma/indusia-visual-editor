"""Phase 10.1 spike — `ais` CLI smoke check.

Documents that the operator host running indusia-visual-editor in production
MUST have `auto-inspect-service` installed so the `ais` CLI is on PATH.
Skips when `ais` isn't installed locally (the dev environment doesn't
require it — only the production host pushing weights does).

See `docs/specs/ais-model-push.md` for the full interface contract and
the multi-step add→commit→push flow our wrapper implements.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest


_AIS_PATH = shutil.which("ais")


@pytest.mark.skipif(
    _AIS_PATH is None,
    reason=(
        "ais CLI not installed; see docs/specs/ais-model-push.md for install "
        "procedure. Production hosts MUST have it; dev hosts may skip."
    ),
)
def test_ais_cli_responsive_to_help():
    """If `ais` is on PATH, it must at minimum respond to --help.

    A binary on PATH that returns non-zero on --help signals an environment
    bug (broken install, missing entry-point, wrong shebang). Production
    rollout MUST gate on this passing.
    """
    result = subprocess.run(
        [_AIS_PATH, "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"ais --help returned {result.returncode}; stderr={result.stderr[:300]!r}"
    )
    # The CLI's top-level help mentions the `model` subcommand we depend on.
    assert "model" in result.stdout.lower(), (
        f"ais --help output missing 'model' subcommand: {result.stdout[:300]!r}"
    )
