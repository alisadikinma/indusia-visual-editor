"""Async subprocess wrapper for `ais model {add,commit,push}`.

The flow is documented in `docs/specs/ais-model-push.md`. Each step
short-circuits on non-zero exit so the `PushResult.stage` field records
which step failed — the operator re-runs from the failing step without
re-staging already-good files.

The subprocess factory is overridable via `set_subprocess_factory` so
tests never spawn a real `ais` binary. Production calls go through
`asyncio.create_subprocess_exec` directly.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal


# Subprocess factory signature: (*argv, cwd, stdout, stderr) -> Process-like
_SubprocessFactory = Callable[..., Awaitable[Any]]


async def _default_factory(*argv: str, cwd: str | None = None, **kwargs: Any):
    return await asyncio.create_subprocess_exec(
        *argv,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )


_subprocess_factory: _SubprocessFactory = _default_factory


def set_subprocess_factory(factory: _SubprocessFactory) -> None:
    """Test seam — inject a fake subprocess factory."""
    global _subprocess_factory
    _subprocess_factory = factory


def reset_subprocess_factory() -> None:
    global _subprocess_factory
    _subprocess_factory = _default_factory


Stage = Literal["add", "commit", "push", "done", "timeout"]


@dataclass
class PushResult:
    """Outcome of a `push_model` invocation.

    `stage` records where the sequence terminated. On success it's
    `"done"`. On failure it's the failing step (`add` / `commit` / `push`),
    or `"timeout"` if a step hung past the configured budget.
    """

    ok: bool
    stage: Stage
    returncode: int
    stdout: str
    stderr: str


async def _run_step(
    *argv: str,
    cwd: Path,
    timeout: float,
) -> tuple[int, str, str, bool]:
    """Run one subprocess step. Returns (returncode, stdout, stderr, timed_out)."""

    proc = await _subprocess_factory(
        *argv,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", f"{argv[0]} {argv[1] if len(argv) > 1 else ''} timed out", True
    rc = proc.returncode if proc.returncode is not None else -1
    return (
        rc,
        out.decode("utf-8", errors="replace") if out else "",
        err.decode("utf-8", errors="replace") if err else "",
        False,
    )


async def push_model(
    *,
    pcb_name: str,
    commit_message: str,
    registry_root: Path,
    ais_binary: str = "ais",
    timeout: float = 300.0,
) -> PushResult:
    """Run `ais model add --all` → `commit -m <msg>` → `push` in sequence.

    All three steps run with `cwd=registry_root` — the `ais` CLI expects
    to be invoked inside the model-registry git repo. Auth (Git +
    Git-LFS credentials) is the operator's responsibility per
    `docs/specs/ais-model-push.md`; this wrapper only captures the
    subprocess exit code + stderr for the audit trail.

    The function never raises on subprocess failure — it ALWAYS returns
    a PushResult so the route layer can persist a deployment row with
    full provenance regardless of outcome.
    """

    steps: list[tuple[Stage, tuple[str, ...]]] = [
        ("add", (ais_binary, "model", "add", pcb_name, "--all")),
        ("commit", (ais_binary, "model", "commit", "-m", commit_message)),
        ("push", (ais_binary, "model", "push")),
    ]

    for stage, argv in steps:
        rc, stdout, stderr, timed_out = await _run_step(
            *argv, cwd=registry_root, timeout=timeout
        )
        if timed_out:
            return PushResult(
                ok=False,
                stage="timeout",
                returncode=-1,
                stdout=stdout,
                stderr=stderr or f"step '{stage}' exceeded {timeout}s",
            )
        if rc != 0:
            return PushResult(
                ok=False,
                stage=stage,
                returncode=rc,
                stdout=stdout,
                stderr=stderr,
            )

    return PushResult(
        ok=True,
        stage="done",
        returncode=0,
        stdout="",
        stderr="",
    )
