# `ais model push` — interface spec (Phase 10.1 spike)

> **Status:** verified against `auto-inspect-service` HEAD `D:\Projects\Indusia-Inspection\auto-inspect-service\src\auto_inspect_service\cli\commands\model.py` on 2026-05-23.

## TL;DR — plan correction

The M10 plan (`docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md` §M10 + Phase 10.3) describes the command shape as:

```
ais model push <name> --version <semver>
```

**This is incorrect.** There is no `--version` flag and `push` takes no positional arguments. Versioning is handled by git+LFS history (each `ais model commit` is a new version; the operator labels the commit message).

The real flow is **three commands**, run sequentially in the model-registry working directory:

```bash
ais model add <pcb_name> --all      # stage all component files (weights, configs, assets)
ais model commit -m "<message>"     # commit staged files locally
ais model push                      # push local commits to the remote (GitLab + LFS)
```

`indusia-visual-editor`'s `services/deploy/registry.py` implements exactly this sequence as three `asyncio.create_subprocess_exec` calls in order. If any step exits non-zero, the deployment is marked `failed` with the failing step's stderr captured in `deployments.error_text`.

## Working directory requirement

`ais model {add,commit,push}` all require the current working directory to be **inside the model-registry git repository**. The registry path is configured via `ais model setup` once per machine (writes `~/.config/ais/registry.yaml`).

For the indusia-visual-editor deployment service, the working directory is `IVE_REGISTRY_ROOT` (new env var, defaults to `./registry`). The operator runs `ais model setup` once on the host before any promote happens.

## Auth requirement

`ais model push` invokes `git push origin <branch>` internally with `git-credential-manager` (Windows) or the configured Git credential helper. LFS objects use the same auth via `git-lfs`.

For first-time setup on a new host:

```bash
git config --global credential.helper manager-core
git lfs install
# Then: ais model setup (paste GitLab token when prompted)
```

The indusia-visual-editor service does NOT prompt for credentials — if auth fails, the subprocess returns non-zero and stderr is captured.

## Stdout / stderr format

`add`, `commit`, `push` all use rich console output via `_console()`. Success markers:

| Command | Success marker (stdout) | Failure marker (stderr) |
|---|---|---|
| `add` | `Staged N path(s)` | `Error: Specify components or use --all` |
| `commit` | `Committed: <8-char-sha> <message>` | `Nothing to commit.` (treated as benign no-op by our wrapper) |
| `push` | `Push successful.` | `Push failed: <RegistryError>` |

The indusia-visual-editor wrapper does NOT parse stdout for these markers — it relies solely on the subprocess exit code. The stdout is captured for inclusion in the deployment row's audit log.

## Typical duration

- `add --all`: <2s for a typical PCB (50-100 component files)
- `commit`: <1s
- `push`: 5-60s depending on LFS object size + network. The default service-side `asyncio` timeout for the full sequence is `IVE_AIS_PUSH_TIMEOUT_SECS=300` (5 min — enough headroom for slow LFS pushes; raise on first miss).

## Installation check

`ais` is not installed in the indusia-visual-editor dev environment by default — the spike smoke test at `tests/spike/test_ais_cli_available.py` skips when `ais` isn't on PATH. Production deploys (M14) MUST install it via:

```bash
pip install -e D:/Projects/Indusia-Inspection/auto-inspect-service
# Or conda: ./scripts/install-conda.ps1 inside auto-inspect-service
```

## Implementation surface in `indusia-visual-editor`

```python
# services/deploy/registry.py
async def push_model(
    pcb_name: str,
    commit_message: str,
    *,
    registry_root: pathlib.Path,
    timeout: float = 300.0,
) -> PushResult:
    """Run `ais model add --all` → `commit -m ...` → `push` in sequence.

    Returns PushResult(ok: bool, stage: str, stdout: str, stderr: str).
    stage is the step that produced the terminal status — useful when
    `add` succeeds but `push` fails (network), so the operator can
    re-run from `push` without re-staging.
    """
```

`stage` values: `"add"`, `"commit"`, `"push"`, `"done"` (all green).

This shape is opaque to the route layer — `routes/deploy.py` only cares about `ok` + the captured logs for the audit trail.
