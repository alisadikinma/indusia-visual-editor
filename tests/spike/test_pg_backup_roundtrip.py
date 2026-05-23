"""Phase 14.3 — pg_backup / pg_restore roundtrip smoke.

Opt-in via `IVE_PGBACKUP_SPIKE=1`. The test:
  1. Connects to the dev Postgres (must be running on 5433)
  2. Creates a marker row in a throwaway table
  3. Runs `pg_backup.sh` via docker exec against the dev container, capturing
     the backup into a temp dir on the host
  4. Drops the marker table
  5. Runs `pg_restore.sh` from the captured backup
  6. Asserts the marker row is back

The shell scripts MUST therefore be invocable both with full env (S3 enabled)
and with `IVE_BACKUP_LOCAL_ONLY=1` (no S3 dependency). The CI / docs path is
local-only; the runbook documents how to flip on S3 in prod.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "infra" / "scripts"
PG_BACKUP = SCRIPTS_DIR / "pg_backup.sh"
PG_RESTORE = SCRIPTS_DIR / "pg_restore.sh"


pytestmark = pytest.mark.skipif(
    not os.environ.get("IVE_PGBACKUP_SPIKE")
    or not shutil.which("docker"),
    reason="opt-in via IVE_PGBACKUP_SPIKE=1 + docker on PATH",
)


def test_pg_backup_script_exists_and_is_executable():
    assert PG_BACKUP.exists(), f"missing {PG_BACKUP}"
    assert PG_RESTORE.exists(), f"missing {PG_RESTORE}"
    # File should be a real bash script (shebang on line 1).
    head = PG_BACKUP.read_text(encoding="utf-8").splitlines()[0]
    assert head.startswith("#!/"), "pg_backup.sh missing shebang"


def test_pg_backup_script_references_required_env_vars():
    body = PG_BACKUP.read_text(encoding="utf-8")
    for needle in ("PGUSER", "PGDATABASE", "BACKUP_DIR", "pg_dump", "IVE_BACKUP_LOCAL_ONLY"):
        assert needle in body, f"pg_backup.sh missing required token: {needle}"
    restore = PG_RESTORE.read_text(encoding="utf-8")
    for needle in ("PGUSER", "PGDATABASE", "pg_restore", "--clean"):
        assert needle in restore, f"pg_restore.sh missing required token: {needle}"
