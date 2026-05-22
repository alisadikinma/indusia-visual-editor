"""Phase 4.4 - atomic graphflow model directory writer.

write_model_dir builds the full {config, locations, settings,
components/, assets/} tree under a tempdir, then atomically moves
it into place. Pre-existing target dir is backed up to
<name>.bak-<timestamp>, never silently overwritten.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from indusia_visual_editor.services.adapter.writer import write_model_dir


@pytest.fixture
def sample_inputs():
    top_config = {
        "name": "NV80",
        "nodes": {"data": {"type": "input"}, "output": {"type": "merge_result"}},
        "edges": {"data": ["output"]},
    }
    locations = {"frames": [{"frame_id": "TOP-01", "side": "top"}]}
    settings = {"camera": {"gain": 1.0}}
    subgraphs = {
        "R1": {"nodes": {"data": {"type": "input"}}, "edges": {}},
        "C4": {"nodes": {"data": {"type": "input"}}, "edges": {}},
    }
    return top_config, locations, settings, subgraphs


def test_write_model_dir_creates_full_tree(tmp_path: Path, sample_inputs):
    top, loc, settings, subs = sample_inputs
    result = write_model_dir(
        target_root=tmp_path,
        pcb_name="NV80",
        top_config=top,
        locations=loc,
        settings=settings,
        subgraphs=subs,
    )
    assert result == (tmp_path / "NV80").resolve()
    pcb_dir = tmp_path / "NV80"
    assert (pcb_dir / "config.yaml").is_file()
    assert (pcb_dir / "locations.yaml").is_file()
    assert (pcb_dir / "settings.yaml").is_file()
    assert (pcb_dir / "components").is_dir()
    assert (pcb_dir / "components" / "comp-R1.yaml").is_file()
    assert (pcb_dir / "components" / "comp-C4.yaml").is_file()
    assert (pcb_dir / "assets").is_dir()


def test_write_model_dir_yaml_roundtrip(tmp_path: Path, sample_inputs):
    top, loc, settings, subs = sample_inputs
    write_model_dir(
        target_root=tmp_path,
        pcb_name="NV80",
        top_config=top,
        locations=loc,
        settings=settings,
        subgraphs=subs,
    )
    pcb_dir = tmp_path / "NV80"
    assert yaml.safe_load((pcb_dir / "config.yaml").read_text()) == top
    assert yaml.safe_load((pcb_dir / "locations.yaml").read_text()) == loc
    assert yaml.safe_load((pcb_dir / "settings.yaml").read_text()) == settings
    assert yaml.safe_load((pcb_dir / "components" / "comp-R1.yaml").read_text()) == subs["R1"]


def test_write_model_dir_backs_up_existing(tmp_path: Path, sample_inputs):
    top, loc, settings, subs = sample_inputs
    write_model_dir(
        target_root=tmp_path,
        pcb_name="NV80",
        top_config=top,
        locations=loc,
        settings=settings,
        subgraphs=subs,
    )
    write_model_dir(
        target_root=tmp_path,
        pcb_name="NV80",
        top_config=top,
        locations=loc,
        settings=settings,
        subgraphs={"R99": subs["R1"]},
    )
    bak_dirs = list(tmp_path.glob("NV80.bak-*"))
    assert len(bak_dirs) == 1
    assert (tmp_path / "NV80" / "components" / "comp-R99.yaml").is_file()
    assert not (tmp_path / "NV80" / "components" / "comp-R1.yaml").is_file()


def test_write_model_dir_atomicity_on_failure(tmp_path: Path, sample_inputs):
    """If shutil.move fails mid-write, target_root must be unchanged."""
    top, loc, settings, subs = sample_inputs
    target = tmp_path / "NV80"
    assert not target.exists()
    with patch(
        "indusia_visual_editor.services.adapter.writer.shutil.move",
        side_effect=OSError("simulated disk full"),
    ):
        with pytest.raises(OSError):
            write_model_dir(
                target_root=tmp_path,
                pcb_name="NV80",
                top_config=top,
                locations=loc,
                settings=settings,
                subgraphs=subs,
            )
    assert not target.exists()
    assert list(tmp_path.glob("NV80.bak-*")) == []
