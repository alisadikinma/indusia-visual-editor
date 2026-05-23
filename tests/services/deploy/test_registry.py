"""Phase 10.3 — `services/deploy/registry.push_model` subprocess wrapper.

The wrapper runs three `ais model` subprocess calls in sequence:
    1. `ais model add <pcb> --all`     (stage component files)
    2. `ais model commit -m "<msg>"`   (commit staged files locally)
    3. `ais model push`                (push to remote registry)

Each step's exit code gates the next. Any non-zero exit short-circuits the
sequence and the PushResult.stage records WHERE the failure happened so
the operator can re-attempt from the right step (e.g. `add` succeeded,
network blew up during `push` — operator re-runs from `push` not `add`).

Tests use a fake subprocess factory injected via
`set_subprocess_factory` so we never spawn a real `ais` binary in CI.
Opt-in integration against real `ais` is gated behind
`IVE_AIS_INTEGRATION` (mirrors Ollama/inspect-service opt-in pattern).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from indusia_visual_editor.services.deploy.registry import (
    PushResult,
    push_model,
    reset_subprocess_factory,
    set_subprocess_factory,
)


class _FakeProc:
    """asyncio.subprocess.Process double — communicate() returns the
    scripted bytes and returncode."""

    def __init__(self, returncode: int, stdout: bytes, stderr: bytes) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(
        self, _input: bytes | None = None
    ) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        pass


class _Recorder:
    """Captures every subprocess invocation for assertions."""

    def __init__(
        self,
        results: dict[tuple[str, ...], tuple[int, bytes, bytes]] | None = None,
    ) -> None:
        # Map from (argv-tuple after binary) -> (returncode, stdout, stderr)
        self.results = results or {}
        self.calls: list[dict] = []

    async def __call__(
        self,
        *argv: str,
        cwd: str | None = None,
        stdout=None,
        stderr=None,
        **_kwargs,
    ) -> _FakeProc:
        self.calls.append({"argv": tuple(argv), "cwd": cwd})
        # Match on the tail (everything after the first arg, which is the binary).
        key = tuple(argv[1:])
        rc, out, err = self.results.get(key, (0, b"ok\n", b""))
        return _FakeProc(rc, out, err)


@pytest.fixture(autouse=True)
def _reset_factory():
    yield
    reset_subprocess_factory()


@pytest.fixture
def tmp_registry(tmp_path):
    root = tmp_path / "registry"
    root.mkdir()
    return root


@pytest.mark.asyncio
async def test_push_model_runs_add_commit_push_sequence_in_order(tmp_registry: Path):
    rec = _Recorder()
    set_subprocess_factory(rec)

    result = await push_model(
        pcb_name="pcb_42",
        commit_message="promote run-abc",
        registry_root=tmp_registry,
        ais_binary="ais",
        timeout=30.0,
    )

    assert isinstance(result, PushResult)
    assert result.ok is True
    assert result.stage == "done"
    assert result.returncode == 0

    # Three subprocess invocations, in order.
    argvs = [c["argv"] for c in rec.calls]
    assert len(argvs) == 3
    assert argvs[0] == ("ais", "model", "add", "pcb_42", "--all")
    assert argvs[1] == ("ais", "model", "commit", "-m", "promote run-abc")
    assert argvs[2] == ("ais", "model", "push")

    # All three ran inside the registry root.
    assert all(str(tmp_registry) == c["cwd"] for c in rec.calls)


@pytest.mark.asyncio
async def test_push_model_short_circuits_on_add_failure(tmp_registry: Path):
    """When `add` fails, commit and push MUST NOT run — staging a broken
    set of files then pushing them would be worse than the original error."""
    rec = _Recorder(
        results={
            ("model", "add", "pcb_42", "--all"): (
                2,
                b"",
                b"Error: pcb_42 not found in registry\n",
            ),
        }
    )
    set_subprocess_factory(rec)

    result = await push_model(
        pcb_name="pcb_42",
        commit_message="x",
        registry_root=tmp_registry,
        ais_binary="ais",
        timeout=30.0,
    )

    assert result.ok is False
    assert result.stage == "add"
    assert result.returncode == 2
    assert "pcb_42 not found" in result.stderr

    # Only ONE subprocess call — the sequence was aborted.
    assert len(rec.calls) == 1


@pytest.mark.asyncio
async def test_push_model_records_push_stage_failure_after_successful_add_and_commit(
    tmp_registry: Path,
):
    """`add` + `commit` succeed, `push` fails (e.g. network down). The
    operator must see stage='push' so they can re-run only the push, not
    the whole sequence."""
    rec = _Recorder(
        results={
            ("model", "push"): (1, b"", b"Push failed: connection refused\n"),
        }
    )
    set_subprocess_factory(rec)

    result = await push_model(
        pcb_name="pcb_42",
        commit_message="x",
        registry_root=tmp_registry,
        ais_binary="ais",
        timeout=30.0,
    )

    assert result.ok is False
    assert result.stage == "push"
    assert result.returncode == 1
    assert "connection refused" in result.stderr

    # All three calls executed in order — push was reached.
    assert len(rec.calls) == 3
    assert rec.calls[2]["argv"][1:] == ("model", "push")


@pytest.mark.asyncio
async def test_push_model_honors_custom_ais_binary_path(tmp_registry: Path):
    """The `ais_binary` config knob allows pinning an absolute path on
    production hosts where PATH may not be set under systemd."""
    rec = _Recorder()
    set_subprocess_factory(rec)

    custom = "/opt/auto-inspect-service/bin/ais"
    await push_model(
        pcb_name="pcb_x",
        commit_message="y",
        registry_root=tmp_registry,
        ais_binary=custom,
        timeout=30.0,
    )

    for c in rec.calls:
        assert c["argv"][0] == custom


@pytest.mark.asyncio
async def test_push_model_times_out_cleanly(tmp_registry: Path):
    """If a step hangs past `timeout`, the wrapper must kill the process
    and return ok=False with stage='timeout' rather than blocking the
    request indefinitely."""

    async def slow_factory(*_argv, cwd=None, stdout=None, stderr=None, **_kw):
        class _Hanging:
            returncode = None

            async def communicate(self, _input=None):
                await asyncio.sleep(10.0)
                return b"", b""

            async def wait(self):
                await asyncio.sleep(10.0)
                return 0

            def kill(self):
                self.returncode = -9

        return _Hanging()

    set_subprocess_factory(slow_factory)

    result = await push_model(
        pcb_name="pcb_slow",
        commit_message="x",
        registry_root=tmp_registry,
        ais_binary="ais",
        timeout=0.05,
    )

    assert result.ok is False
    assert result.stage == "timeout"


# Opt-in integration test — gated behind env var. Skip in CI.
@pytest.mark.skipif(
    not os.environ.get("IVE_AIS_INTEGRATION"),
    reason="set IVE_AIS_INTEGRATION=1 with a real `ais` install + configured registry",
)
@pytest.mark.asyncio
async def test_integration_real_ais_install_responds_to_help():
    """The wrapper relies on the real `ais` CLI being installed. This
    smoke runs `ais --help` directly via the same subprocess factory the
    production wrapper uses — proves the binary is reachable from the
    visual-editor process."""
    proc = await asyncio.create_subprocess_exec(
        "ais",
        "--help",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _err = await proc.communicate()
    assert proc.returncode == 0
    assert b"model" in out.lower()
