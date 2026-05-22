# CLAUDE.md — Indusia Visual Editor

> **Authoritative project memory.** Auto-loaded into every Claude Code session in this directory. Read this BEFORE exploring code, BEFORE making assumptions about existing modules, BEFORE generating new code. Updating this file is mandatory whenever a phase ships new routes, hooks, tables, services, or convention changes.

---

## 1. Project identity

| Field | Value |
|---|---|
| Name | `indusia-visual-editor` |
| One-line | Factory-user-driven PCB inspection platform — BOM + golden sample → production inspection in hours, no YAML, no CLI |
| Primary user | MI division operator / supervisor at PCB factories (non-coder) |
| Repo root | `D:\Projects\indusia-visual-editor` |
| Status | M0 in progress (Phase 0.5 ✓, Phase 0.1 ✓; next: Phase 0.2) |
| Plan | [docs/plans/2026-05-22-visual-editor-mvp.md](docs/plans/2026-05-22-visual-editor-mvp.md) |
| Adoption spec | [docs/specs/label-studio-adoption.md](docs/specs/label-studio-adoption.md) |
| LSF build spec | [docs/specs/lsf-build.md](docs/specs/lsf-build.md) |

## 2. Current implementation state

Only commit history is authoritative — never invent state. As of 2026-05-22:

| Layer | Built | Not yet built |
|---|---|---|
| Backend | `pyproject.toml`, `src/indusia_visual_editor/{__init__,config,main}.py`, `GET /health` | DB, models, all routes besides /health, all services, LLM client, asset storage |
| Tests | `tests/test_health.py` (1 test) | everything else |
| Frontend | none yet | Vue 3 scaffold (Phase 0.3), Dashboard (Phase 1.4), Wizard (Phase 2.3) |
| Docker | none yet | Phase 0.4 |
| DB | none yet | Phase 1.1 (Alembic baseline) |
| LSF | upstream build verified, NOT yet vendored | vendor in M6 Phase 6.1 |

**Anti-hallucination rule:** if it isn't in the file tree or the git log, it doesn't exist. Run `git log --oneline` if uncertain.

## 3. External services (DO NOT modify)

These are sibling repos at `D:\Projects\Indusia-Inspection\`. We HTTP-call them; we never edit their code in v1.

| Service | Port | Role | Reuse pattern |
|---|---|---|---|
| `auto-inspect-service` | 8001 | Inference engine (graphflow + YOLO + Anomalib + fiducial + OCR + barcode) + Git+LFS model registry via `ais model push/pull` | We POST `/api/training/start`, subscribe to its SSE stream, call `/api/models/{name}/load` |
| `auto-inspect-edge` | 8000 | Hardware: PLC + Hikrobot camera, pulls weights via `ais model pull`, receives selected model from `.cache/selected_model.json` | We send refresh webhook only; otherwise untouched |
| `auto-inspect-engine` | (lib) | `BaseEstimator` / `BaseTransform` foundation, RGB everywhere | We do NOT import this directly in v1 — we configure it through service |
| Ollama | 11434 | `gemma4:31b` (20GB, 256K context) on dedicated GPU box | httpx async, structured-output mode |

**Iron law copied from `auto-inspect-engine`:** all custom model classes extend `BaseEstimator` / `BaseTransform`. RGB images everywhere, never BGR.

## 4. Tech stack — LOCKED

Do NOT substitute. If a need arises that doesn't fit, raise it as a plan deviation, never silently swap.

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.10+ (Poetry resolved 3.14.3 on Ali's machine) | `requires-python = ">=3.10,<4.0"` |
| Web framework | FastAPI 0.121+ + uvicorn[standard] | Async-first |
| Config | pydantic-settings 2.x, env prefix `IVE_` | `.env` file optional |
| HTTP client | httpx (async) | NOT `requests` |
| ORM | SQLAlchemy 2.x async + Alembic | Phase 1.1 onward |
| DB | PostgreSQL 16 (Docker Compose) | Phase 0.4 onward |
| SSE | sse-starlette | for training progress relay |
| Image I/O | opencv-python + PyTurboJPEG | match engine |
| LLM client | httpx → Ollama `/api/generate` + `/api/chat`, `format=json` | structured-output validated by pydantic |
| Tests | pytest + pytest-asyncio (auto mode) + httpx ASGITransport | factory-boy when needed |
| Packaging | Poetry 2.x | venv per project |
| Frontend | Vue 3 + Vite + TS + Pinia + Vue Router | Phase 0.3 onward |
| Canvas | LSF (Apache-2.0) vendored at `web/public/lsf/` | NOT custom Konva; see §10 |
| Frontend HTTP | axios + native EventSource | for SSE consumption |
| Styling | Tailwind 3 + tokens from §A.6 of plan | NO ad-hoc colors |
| FE tests | Vitest + @vue/test-utils | |
| Containers | Docker Compose (dev + prod) | Phase 0.4 |
| Reverse proxy (prod) | Traefik (auto HTTPS) | M14 |
| Code style | black + isort + flake8 (Py); biome / eslint + prettier (Vue) | mirror existing services |

## 5. Backend file layout — canonical

This is the target structure. Create files in this exact layout. Do NOT invent alternative paths.

```
src/indusia_visual_editor/
├── __init__.py                 # __version__ source of truth
├── main.py                     # FastAPI app + lifespan + middleware + router wiring
├── config.py                   # AppConfig(BaseSettings), IVE_ prefix
├── routes/
│   ├── __init__.py
│   ├── projects.py             # Phase 1.2
│   ├── assets.py               # Phase 1.3 + 2.2
│   ├── labels.py               # M6
│   ├── training.py             # M7 (Gate 1)
│   ├── deploy.py               # M10 (Gate 2)
│   ├── chat.py                 # M12 advisor SSE
│   ├── llm.py                  # Phase 3.4 planner endpoint
│   ├── ml_backend.py           # M5/v1.5 LSF ML backend protocol
│   └── webhooks.py             # M11 edge integration
├── schemas/                    # pydantic request/response models
│   ├── projects.py
│   ├── assets.py
│   ├── labels.py
│   └── ...
├── services/
│   ├── asset/                  # BOM parser, image store, drawing proc, MI classifier
│   ├── project/                # CRUD + versioning
│   ├── label/                  # LS-JSON validate, region ops, exporter (LS→YOLO)
│   ├── llm/                    # planner, prelabel, judge (v1.5), advisor
│   ├── inspect_scope/          # derive scope+detector_presets from LSF annotation
│   ├── inspect_service/        # httpx client → auto-inspect-service
│   └── deploy/                 # promote-to-prod + edge notify
├── db/
│   ├── __init__.py
│   ├── session.py              # async engine + get_session dep
│   ├── models.py               # SQLAlchemy declarative
│   └── alembic/                # migrations
├── data/                       # YAML data files (taxonomy, detector mapping) — committed
└── utils/
    ├── logging_config.py
    └── responses.py            # success() / failed() — match existing service shape
```

## 6. Backend conventions

### 6.1 Response shape — MANDATORY

EVERY route returns this shape on both success and error paths. Match `auto-inspect-service` helpers exactly.

```python
{
    "status": True | False,
    "message": "human-readable string",
    "data": {...} | None,
}
```

`/health` is the reference: `{"status": True, "message": "ok", "data": {"version": "0.1.0"}}`.

### 6.2 Env vars

All env vars use the `IVE_` prefix. Defaults live in `AppConfig` (`config.py`). The `.env` file is optional and gitignored (`!.env.example` is not; `.env.example` is committed and is the schema doc).

Current keys:
- `IVE_APP_HOST` (default `0.0.0.0`)
- `IVE_APP_PORT` (default `8002`)
- `IVE_LOG_LEVEL` (default `INFO`)

Planned (add to `AppConfig` when needed, never read `os.environ` directly):
- `IVE_DATABASE_URL` — Phase 0.4
- `IVE_OLLAMA_URL` (default `http://localhost:11434`) — Phase 3.1
- `IVE_OLLAMA_MODEL_PLANNER` (default `gemma4:31b`) — Phase 3.1
- `IVE_OLLAMA_MODEL_PRELABEL` — Phase 3.1
- `IVE_OLLAMA_TIMEOUT` (default `120`) — Phase 3.1
- `IVE_INSPECT_SERVICE_URL` (default `http://localhost:8001`) — Phase 7+
- `IVE_STORAGE_ROOT` (default `./storage`) — Phase 1.3

### 6.3 Ports

| Service | Port | Reason |
|---|---|---|
| `auto-inspect-edge` | 8000 | existing |
| `auto-inspect-service` | 8001 | existing |
| **`indusia-visual-editor` (us)** | **8002** | next free slot |
| Ollama | 11434 | upstream default |
| Postgres (dev) | 5432 | Phase 0.4 |
| Vue dev server | 5173 | Vite default |

### 6.4 Async patterns

- All FastAPI route handlers are `async def`
- All DB calls go through `AsyncSession` + `get_session` dependency
- All external HTTP calls use `httpx.AsyncClient`
- Subprocess calls use `asyncio.subprocess` if invoked from a route, never blocking `subprocess.run`

### 6.5 Logging

```python
import logging
logger = logging.getLogger(__name__)
```

Structured fields via `structlog` after M14 (defer until polish). For now stdlib logger with `extra={"project_id": ..., "train_run_id": ...}` is sufficient.

### 6.6 Error handling

All LLM / external-service calls raise typed exceptions:
- `LlmError` — Ollama timeout, JSON parse, validation
- `InspectServiceError` — auto-inspect-service HTTP failure
- `AssetError` — BOM parse, image, storage
- `BomParseError` — specific BOM parse failures (Bahasa Indonesia error messages)

Map these to HTTP responses via FastAPI exception handlers in `main.py`. Mirror `auto-inspect-service` pattern.

### 6.7 Testing

- `tests/` mirrors `src/` structure: `tests/routes/`, `tests/services/`, etc.
- `pytest-asyncio` mode = `auto`, so async tests don't need explicit `@pytest.mark.asyncio`
- HTTP tests use `httpx.AsyncClient` + `ASGITransport(app=app)` — do NOT use `TestClient` (sync)
- DB tests use a separate test DB + transactional rollback fixture (set up in Phase 1.1)
- Fixtures for BOMs / images go in `tests/fixtures/`

## 7. Database schema — planned (Phase 1.1+)

Authoritative only when migrations exist. Until then, this is the design.

```sql
-- Phase 1.1
projects (
  id UUID PK,
  name TEXT,
  slug TEXT UNIQUE,
  status TEXT CHECK (status IN ('drafting','training','deployed','failed')),
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

assets (
  id UUID PK,
  project_id UUID FK → projects,
  kind TEXT CHECK (kind IN ('bom','golden_top','golden_bottom','drawing')),
  path TEXT,        -- relative to IVE_STORAGE_ROOT
  sha256 TEXT,      -- for dedup
  mime TEXT,
  size_bytes BIGINT,
  uploaded_at TIMESTAMPTZ
)

bom_items (
  id UUID PK,
  project_id UUID FK,
  designator TEXT,         -- e.g. "R1"
  value TEXT,              -- e.g. "10kΩ"
  package TEXT,            -- e.g. "0805"
  qty INT,
  position_hint TEXT,
  -- scope (user-controlled in canvas)
  inspect_scope TEXT CHECK (inspect_scope IN ('pending','inspected','skipped')) DEFAULT 'pending',
  mi_likely BOOL,
  component_type TEXT,     -- 'electrolytic_cap','dip_ic','connector','tht_resistor','smd_generic',...
  defect_history_count INT DEFAULT 0,
  extra JSONB              -- preserved BOM columns we don't model
)

-- Phase 3.4+
proposed_pipelines (
  id UUID PK, project_id UUID FK, version INT, dag_json JSONB,
  approved_by UUID, approved_at TIMESTAMPTZ
)

-- M6
labels (
  id UUID PK, project_id UUID FK, version INT,
  side TEXT CHECK (side IN ('top','bottom')),
  ls_json JSONB,           -- exact LS-JSON shape from LSF onSubmit
  snapshot_at TIMESTAMPTZ
)

-- M7
train_runs (
  id UUID PK, project_id UUID FK, label_version INT,
  service_job_id TEXT, status TEXT,
  metrics_json JSONB,      -- includes per-component F1, not just global
  started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ
)

-- M10
deployments (
  id UUID PK, project_id UUID FK, train_run_id UUID FK,
  model_version TEXT, edges_notified JSONB, deployed_at TIMESTAMPTZ
)

-- M12
chat_sessions (id UUID PK, project_id UUID FK, messages_json JSONB, created_at TIMESTAMPTZ)
```

UUID PKs, timezone-aware timestamps, FKs with `ON DELETE CASCADE` only when explicitly justified.

## 8. Domain glossary — DO NOT MISUSE

| Term | Meaning | Common confusion |
|---|---|---|
| **PCB** | Printed Circuit Board | not "PCBA"; the bare board |
| **SMT** | Surface Mount Technology — auto pick-and-place, AOI machine handles inspection | EXISTING AOI covers this; we do NOT replace it |
| **MI** | Manual Insertion — through-hole + wave solder, **no inspection automation today** | **OUR PRIMARY TARGET** |
| **AOI** | Automated Optical Inspection (machine on SMT line) | sibling to us; we are AOI-equivalent for MI |
| **BOM** | Bill of Materials, 200-400 rows | NOT the same as inspect-list (5-50 rows) |
| **inspect-list** | subset of BOM the operator chose to inspect | derived from canvas annotation, not BOM directly |
| **designator** | per-component label like `R1`, `C4`, `U7` | regex `^[A-Z]+[0-9]+$`; multi-designator BOM rows (`R1, R2, R3`) expand to 3 rows |
| **golden sample** | photograph of a known-good PCB (top + bottom sides) | reference for training |
| **drawing** | PCB layout drawing (JPG/PNG only in v1; no Gerber/ODB++) | spatial prior for pre-label |
| **fiducial** | alignment mark on PCB (usually 3 corners) | tracked as `KeyPointLabels` in LSF |
| **graphflow DAG** | node-graph pipeline config in `auto-inspect-service` | per-PCB `config.yaml` + `components/*.yaml` |
| **Gate 1** | HITL approval before training starts | hard stop; user clicks "Start Training" |
| **Gate 2** | HITL approval before pushing weights to edges | hard stop; user clicks "Promote to Production" |

### Defect criteria (user picks per-region in canvas)

`missing_component`, `orientation`, `polarity_flip`, `connector_pin_bending`, `missing_pin_connector`, `lifted_pin`, `wrong_value`, `misalignment`, `solder_short` (whole-side mode only).

Mapping criterion → detector preset lives in `data/defect_detector_mapping.yaml` (Phase 2.2c). Single source of truth.

## 9. LLM — Gemma 4 (Ollama)

### 9.1 The four roles

| Role | Trigger | Phase | Output schema |
|---|---|---|---|
| Pipeline planner | user clicks "🤖 Build inspection pipeline" after labeling | M4 | `ProposedPipeline` |
| Pre-label assistant | user opens LabelingCanvas with no annotations yet | M5 | `list[PreLabeledRegion]` |
| Runtime defect judge | edge sends ROI crop for borderline cases | **v1.5 (NOT in MVP)** | `DefectVerdict` |
| Training/diagnostics advisor | user opens chat drawer | M12 | `ChatTurn` (streamed) |

### 9.2 Structured output contract

ALL Gemma calls use `format=json` + pydantic validation. Never trust raw text. Schemas live in `services/llm/schemas.py`. If validation fails, raise `LlmError`, never accept the malformed output.

```python
class ProposedPipelineStep(BaseModel):
    designator: str                    # regex ^[A-Z]+[0-9]+$
    component_type: str
    detectors: list[Literal["yolo","anomalib","ocr","barcode","template_match"]]
    reasoning: str

class ProposedPipeline(BaseModel):
    pcb_model: str
    fiducial_strategy: Literal["circle","orb","yolo","threshold"]
    steps: list[ProposedPipelineStep]

class PreLabeledRegion(BaseModel):
    designator: str
    bbox: tuple[float, float, float, float]  # x, y, w, h normalized 0-1
    confidence: float
    side: Literal["top","bottom"]

class DefectVerdict(BaseModel):
    verdict: Literal["pass","fail","uncertain"]
    confidence: float
    reason_short: str
    reason_detail: str
```

### 9.3 Performance budget (acceptance criteria)

| Call | Target | Notes |
|---|---|---|
| Planner | ≤30s | full BOM + golden image multi-MB |
| Pre-label | ≤60s | golden + drawing + BOM list |
| Judge | ≤2s | per ROI, runtime hot path — v1.5 only |
| Advisor | streaming, first token <3s | UX requirement |

## 10. LSF integration — boundary

LSF is a **third-party Apache-2.0 library** we vendor as a built artifact at `web/public/lsf/`. We DO NOT modify upstream LSF code. We DO NOT adopt Label Studio's Django backend, datamanager, UI library, schema, RBAC, or storage adapters.

### What we use
- `window.LabelStudio` class instantiated on a div in `LSFEmbed.vue` (React island in Vue 3)
- Declarative XML labeling config (composed per PCB from BOM + Gemma plan)
- Native LS-JSON output (zero adapter for storage; YOLO export is custom)
- ML Backend protocol — **deferred to v1.5** (v1 bakes predictions into task JSON)

### What we replace
- Dashboard, project wizard, BOM parser, planner UI, train/eval/deploy views, chat — all bespoke Vue 3 in our app

### Vendor commands
See `docs/specs/lsf-build.md`. Production build is `MODE=standalone yarn nx run editor:build:production` (NOT the spec's outdated `yarn lsf:build`). Output dir is `web/dist/libs/editor/` (NOT `web/libs/editor/dist/`). Vendor the ENTIRE tree (chunks, WASM, fonts) minus maps and demo media.

### Loading in our HTML
```html
<link rel="stylesheet" href="/lsf/main.css">
<script type="module" src="/lsf/main.js"></script>
```

After load: `window.LabelStudio` is a function. `instanceOptions.reactVersion: 'v18'` required.

## 11. Two HITL gates — hard stops

| Gate | When | UI requirement |
|---|---|---|
| **Gate 1** | Before `auto-inspect-service /api/training/start` is called | Preview: dataset stats, AI-suggested epochs/augmentation. User must click "Start Training" button. |
| **Gate 2** | Before `ais model push` (promote weights to production registry) | Preview: eval metrics (mAP, per-component F1), sample predictions. User must click "Promote to Production" button. |

Never auto-approve. No "auto-continue if metrics > threshold" in v1.

## 12. Anti-AI-slop rules

Code, commit messages, UI strings, and docs.

| Forbidden | Use instead |
|---|---|
| "leverage", "synergies", "paradigm shift", "revolutionary", "game-changer" | concrete verbs and nouns |
| emoji as icons (UI) | Lucide React icons, 1.5px stroke |
| emoji in code (`# 🚀 deploy`) | plain comment if needed at all |
| "TODO", "FIXME", "placeholder", "dummy", "mock" left in shipped code | resolve or ask user before commit |
| corporate hype ("game-changing AI") | factual description |
| `console.log` left in JS | `if (import.meta.env.DEV) console.debug(...)` |
| Bahasa "Inggris-tinggi" like "sinergi", "leverage", "revolusi" in UI copy | "kerja sama", "manfaatkan", concrete verbs |
| commit message starting with "Update" or "Fix stuff" | imperative + scope: `feat(bom): parse Excel with multi-designator expansion` |

UI default language: **Bahasa Indonesia**, technical terms English. No emoji in UI strings. No translation of designators / component names / field names / API identifiers.

## 13. Path conventions

- **Windows backslash** for filesystem paths in code comments and docs (Ali's machine)
- **Forward slash** for URLs, S3 keys, Git paths
- All env paths normalized via `pathlib.Path` in Python code; never string-concat paths
- Storage layout: `storage/{project_id}/{kind}/{sha256}.{ext}` (see Phase 1.3)

## 14. Build, test, run — current commands

```powershell
# One-time setup
$env:PATH = "$env:PATH;C:\Users\alisa\.local\bin"   # add poetry to PATH
Set-Location D:\Projects\indusia-visual-editor
poetry install

# Run tests
poetry run pytest -v

# Boot service (Phase 0.1+; reloads on src/ changes when --reload added)
poetry run uvicorn indusia_visual_editor.main:app --host 0.0.0.0 --port 8002

# Smoke /health
Invoke-WebRequest http://127.0.0.1:8002/health -UseBasicParsing
```

## 15. Reference paths (DO NOT hardcode in code — only in docs/scripts)

| What | Path |
|---|---|
| Existing inspection stack | `D:\Projects\Indusia-Inspection\` |
| auto-inspect-service configs | `D:\Projects\Indusia-Inspection\auto-inspect-service\prod\configs\{pcb_id}\` |
| Label Studio upstream repo (LSF source) | `D:\Projects\label-studio\` |
| LSF built artifact | `D:\Projects\label-studio\web\dist\libs\editor\` (re-build via §10) |
| This project | `D:\Projects\indusia-visual-editor\` |
| User's Obsidian vault | `D:\Obsidian-Vault\` (decision log + cross-project memory) |

## 16. What NOT to do — top anti-hallucination guardrails

1. **Do not invent hooks, components, or routes.** Check the actual file tree first. As of 2026-05-22 only `/health` exists.
2. **Do not assume a DB schema exists.** Phase 1.1 hasn't run. No tables exist yet. Migrations live in `alembic/versions/` and are authoritative.
3. **Do not modify `D:\Projects\Indusia-Inspection\` or `D:\Projects\label-studio\`** from this project. They are sibling repos with their own lifecycle.
4. **Do not fork LSF.** We vendor the built artifact; no source-level changes.
5. **Do not substitute mock data for real integrations.** If a hook / service / table doesn't exist, raise it as a blocker and ask. See gaspol-execute Iron Laws.
6. **Do not commit secrets.** `.env` is gitignored; only `.env.example` is committed.
7. **Do not change Python version requirements** without flagging — `requires-python = ">=3.10,<4.0"` is locked.
8. **Do not use sync `requests` or `psycopg2`** in route handlers. Async-first stack.
9. **Do not skip TDD gate** in plan phases. Every phase step 1 is "Write failing test". If a phase plan doesn't have it, raise it as a plan template violation.
10. **Do not skip CLAUDE.md.** Read this file every session start. Update it when shipping new routes / hooks / tables / conventions.

## 17. Update protocol for this file

When a phase ships new artifacts, append to the relevant section here in the same PR/commit. Example:

- Phase 1.1 ships → update §7 ("Built" column for `projects/assets/bom_items` tables) and §16 ("DB schema exists; check migrations" instead of "no tables")
- Phase 0.3 ships → update §2 (frontend status), add §5b (frontend file layout), update §14 (frontend dev commands)
- Adoption-spec corrections → propagate to §10 (LSF integration boundary)

This file is the single source of truth for "what is true now". If reality diverges, fix this file BEFORE writing more code.
