"""Phase 4.4 - atomic graphflow model directory writer.

Builds the full tree under a tempdir first, backs up any pre-existing
target to <name>.bak-<UTC_timestamp>, then shutil.move's the new tree
into place. Atomic in the sense that a partial write never appears
under target_root - either the new tree is fully there or it isn't.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml


def _write_yaml(path: Path, data: Any) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_model_dir(
    *,
    target_root: Path,
    pcb_name: str,
    top_config: dict,
    locations: dict,
    settings: dict,
    subgraphs: dict[str, dict],
) -> Path:
    """Write a graphflow model directory atomically.

    Args:
        target_root: parent dir where ``<pcb_name>/`` will land.
        pcb_name: directory name; must already be sanitized by caller.
        top_config: shape ``{name, nodes, edges}`` per spike section 1.
        locations: ``{frames: [...]}`` per spike section 4 locations.yaml.
        settings: ``{camera: ..., lighting: ...}`` per spike section 4.
        subgraphs: ``{designator: {nodes, edges}}`` per spike section 2.

    Returns:
        Resolved absolute Path to the final pcb_name directory.

    Raises:
        OSError: any filesystem failure; target_root is unchanged on failure.
    """
    target_root.mkdir(parents=True, exist_ok=True)
    final_dir = (target_root / pcb_name).resolve()

    with tempfile.TemporaryDirectory(prefix="ive-adapter-") as tmp_str:
        tmp_root = Path(tmp_str)
        staged = tmp_root / pcb_name
        (staged / "components").mkdir(parents=True, exist_ok=True)
        (staged / "assets").mkdir(exist_ok=True)

        _write_yaml(staged / "config.yaml", top_config)
        _write_yaml(staged / "locations.yaml", locations)
        _write_yaml(staged / "settings.yaml", settings)
        for designator, subgraph in subgraphs.items():
            _write_yaml(staged / "components" / f"comp-{designator}.yaml", subgraph)

        backup_dir: Path | None = None
        if final_dir.exists():
            ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            backup_dir = final_dir.with_name(f"{pcb_name}.bak-{ts}")
            shutil.move(str(final_dir), str(backup_dir))

        try:
            shutil.move(str(staged), str(final_dir))
        except OSError:
            if backup_dir is not None and backup_dir.exists():
                shutil.move(str(backup_dir), str(final_dir))
            raise

    return final_dir
