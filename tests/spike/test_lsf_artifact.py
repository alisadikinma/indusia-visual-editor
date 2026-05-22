"""Phase 6.1 verification: ensure LSF bundle has been vendored into web/public/lsf/.

The Vue 3 wrapper at `web/src/components/LSFEmbed.vue` (M6 Phase 6.4) loads
LSF as a third-party React island via `<script>` tags pointing at `/lsf/main.js`
and `<link>` at `/lsf/main.css`. Those files must physically exist under the
Vite public root so the dev server and the production build both serve them
unchanged.

The vendoring source is the upstream build artifact at
`D:\\Projects\\label-studio\\web\\dist\\libs\\editor\\` (per CLAUDE.md §10
and `docs/specs/lsf-build.md`). The vendor script
`scripts/vendor-lsf.ps1` mirrors that tree minus source maps and demo media.

These tests do NOT exercise LSF at runtime — that is M6 Phase 6.4's Vitest
suite. Here we only assert the build artifact exists, the entry files are
present and non-trivial in size, and the manifest records sha256 for each
file (so a future drift in upstream produces a deterministic diff).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LSF_DIR = REPO_ROOT / "web" / "public" / "lsf"
MANIFEST = LSF_DIR / "manifest.json"


def test_lsf_main_js_present_and_substantial() -> None:
    main_js = LSF_DIR / "main.js"
    assert main_js.is_file(), f"missing vendored LSF entry: {main_js}"
    # Upstream main.js is ~600KB minified; gate at 100KB to catch truncation.
    assert main_js.stat().st_size > 100 * 1024, (
        f"main.js too small ({main_js.stat().st_size} bytes) — likely truncated copy"
    )


def test_lsf_main_css_present() -> None:
    main_css = LSF_DIR / "main.css"
    assert main_css.is_file(), f"missing vendored LSF stylesheet: {main_css}"
    assert main_css.stat().st_size > 1024, "main.css suspiciously small"


def test_lsf_no_source_maps_committed() -> None:
    maps = list(LSF_DIR.glob("*.map"))
    assert maps == [], f"source maps should not be vendored: {maps}"


def test_lsf_no_demo_media_committed() -> None:
    # Upstream ships ~30MB of demo audio/video/photos under public/files/
    # and public/images/ — we don't want them in the repo or the Docker image.
    demo_files = LSF_DIR / "public" / "files"
    demo_images = LSF_DIR / "public" / "images"
    assert not demo_files.exists(), f"demo media leaked: {demo_files}"
    assert not demo_images.exists(), f"demo media leaked: {demo_images}"


def test_lsf_manifest_records_sha256_per_file() -> None:
    assert MANIFEST.is_file(), f"missing vendor manifest: {MANIFEST}"
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "manifest must be a JSON object"
    assert "files" in data and isinstance(data["files"], dict), "manifest.files missing"
    assert "main.js" in data["files"], "manifest missing main.js entry"
    assert "main.css" in data["files"], "manifest missing main.css entry"
    for relpath, entry in data["files"].items():
        assert "sha256" in entry, f"manifest entry {relpath} missing sha256"
        assert len(entry["sha256"]) == 64, f"{relpath}: sha256 must be 64 hex chars"
        assert "size" in entry, f"manifest entry {relpath} missing size"


@pytest.mark.parametrize("chunk", ["131.js", "29.js", "352.js", "616.js", "710.js"])
def test_lsf_code_split_chunks_present(chunk: str) -> None:
    path = LSF_DIR / chunk
    assert path.is_file(), f"missing LSF code-split chunk: {path}"


def test_lsf_wasm_present() -> None:
    wasm = LSF_DIR / "decode-audio.wasm"
    assert wasm.is_file(), f"missing LSF WASM asset: {wasm}"


def test_lsf_fonts_present() -> None:
    fonts = list(LSF_DIR.glob("*.ttf"))
    assert len(fonts) >= 2, f"expected >=2 Figtree TTF files, got {fonts}"
