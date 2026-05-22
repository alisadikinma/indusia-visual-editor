# Indusia Visual Editor — MVP Design (Hybrid Plan)

> Status: **Design locked, awaiting `gaspol-plan` to append Implementation Plan**
> Date: 2026-05-22
> Author: Ali Sadikin + Claude Code (gaspol-brainstorm)

---

## Design

### 1. Problem

Existing inspection stack (`auto-inspect-edge` / `-engine` / `-service` at `D:\Projects\Indusia-Inspection`) is **engineer-driven**: each new PCB requires hand-written `config.yaml` + `locations.yaml` + `settings.yaml` graphflow DAGs, offline labeling, CLI-triggered training, manual Git+LFS weight push. Onboarding a new PCB model takes days and requires Python + computer-vision domain expertise.

Goal: ship a **factory-user-driven** platform where a manufacturing engineer (non-coder) can take a brand-new PCB from photo → production inspection in hours, without touching YAML or CLI. Cover labeling, training, and edge deployment in a guided UI, with a pervasive multimodal AI assistant (Gemma 4) doing the heavy lifting.

### 1.5 Production-line context (CRITICAL scope clarifier)

PCB produksi customer punya 2 stage:

```
PCB ─▶ SMT line (auto pick-and-place)  ─▶  mesin AOI existing  ✅ (sudah handled, BUKAN scope kita)
                                            │
                                            ▼
       MI / Dipping line (manual insert + wave solder)  ─▶  ⚠️ NO inspection automation  ◀── KITA DI SINI
                                                              (visual editor = AOI-equivalent for MI)
```

**Primary target user = MI division operator/supervisor.** Komponen MI typical: electrolytic capacitor besar, through-hole resistor, header/connector, transformer, switch, DIP IC, jumper wire, heatsink, terminal. Defect MI typical: **lifted pin** (wave solder), **misalignment** (manual placement skew), **polarization flip** (electrolytic cap), **missing component**, **wrong value** (operator pasang R salah), **solder bridge** (post-dipping).

**SMT components also inspectable** — existing AOI mungkin tidak cover semua, atau user mau selective second-check SMT components (e.g., critical IC orientation atau resistor value spot-check). Visual editor support keduanya; user decides per-region in canvas.

**BOM ≠ inspect-list.** BOM punya 200–400 line items (SMT + MI + mekanik); inspect-list typically 5–50 items (mix MI mostly + selective SMT). User pilih fleksibel:
- Default smart-select: MI-likely components (auto-derived dari `bom_items.mi_likely` heuristic per Phase 2.2b)
- Manual override: tambah/buang SMT atau MI sesuai kebutuhan project
- Bulk action: "Select all MI-likely" / "Select connectors only" / "Select from defect history"

**Existing `auto-inspect-engine` sudah punya `lifted_pin` + `border_alignment` detector** (lihat `models/custom/`) — ini konfirmasi factory awareness terhadap MI defect taxonomy. Visual editor expose ini sebagai built-in preset, bukan reinvent.

### 2. Locked decisions (from brainstorm + revisions)

| # | Decision | Rationale |
|---|---|---|
| 1 | **Embed Label Studio Frontend (LSF, Apache-2.0) as React island in Vue 3** — output LS-JSON native (revised from "custom canvas") | Free ~3 weeks of canvas work; LSF already mature on Konva. See [`label-studio-adoption.md`](../specs/label-studio-adoption.md) |
| 2 | MVP scope = label → train → auto-deploy edge (no new HMI screen) | Reuse existing edge UI; ship faster |
| 3 | Multi-model graphflow DAG per PCB (YOLO + Anomalib + others) | Match `auto-inspect-engine` Iron Law |
| 4 | Gemma 4 (Ollama) plays **4 roles**: pipeline planner, auto pre-label, runtime defect judge, training advisor | One brain across platform |
| 5 | New top-level service `indusia-visual-editor` (FastAPI), HTTP-call existing `auto-inspect-service` | Clean SoC, existing services untouched |
| 6 | Dedicated GPU server for Ollama **gemma4:31b** (20GB, 256K context) | Best reasoning quality; no resource contention with training |
| 7 | Inputs: BOM Excel/CSV + JPG/PNG golden sample (top+bottom) + JPG/PNG drawing | Realistic for factory operators (no Gerber dependency v1) |
| 8 | **2 HITL gates**: (a) approve before training starts, (b) approve before edge deploy | Safest path to production |
| 9 | Architecture **Path A** — Lean monolith + Ollama-direct calls, LLM logic isolated in `services/llm/` module | Fastest MVP, refactor to microservices later if needed |
| 10 | **Scope = user-controlled per-region in canvas** — Gemma auto-pre-labels ALL BOM designators (SMT + MI + mekanik); user per-region toggles inspect/skip. MI/SMT classifier is a **default visual hint only** (badge color, sort, smart-select shortcut), NOT a hard filter. SMT components CAN be inspected if user opts in (existing AOI may not cover everything, or user wants second-check selective SMT). | Trust user judgment; smart defaults with full override. Primary user = MI, but flexibility for selective SMT inspection. |
| 11 | **MI-typical detector presets** mapped from defect criteria — user picks criteria per region in canvas; backend translates criteria→detector preset via `defect_detector_mapping.yaml` | Single source of truth = canvas annotation; predictable mapping, auditable |
| 12 | **Unified canvas UX** — Gemma 4 auto-pre-labels ALL BOM designators on golden; user reviews bbox+class, then per-region picks `inspect_scope` (inspect/skip) + `defect_criteria` (multi-select); skipped regions dim. Single LSF config with `<RectangleLabels>` + `<Choices perRegion>` × 2 | Replaces separate wizard "scope filter" step and separate inspection-spec-PDF parser. Simpler mental model. |
| 13 | **Inspection-form PDF parser deferred to v1.5** — described in [`inspection-spec-document-v1.5.md`](../roadmap/inspection-spec-document-v1.5.md) but not built in v1; v1 derives scope+criteria from canvas annotations only | YAGNI — many customers do not have such forms, canvas works for everyone |

### 3. Architecture diagram

```
┌──────────────────────────────────────────────────────────┐
│  Browser — Vue 3 + Konva.js + Pinia                      │
│  Dashboard · Wizard · Canvas · Train/Eval · Deploy       │
└────────────────────────┬─────────────────────────────────┘
                         │ HTTPS / REST + SSE
                         ▼
┌──────────────────────────────────────────────────────────┐
│  indusia-visual-editor (FastAPI, single deploy unit)      │
│                                                           │
│  routes/      project · asset · label · train · deploy   │
│               · chat · webhook                            │
│  services/                                                │
│    asset/     BOM parser, image storage, drawing render  │
│    project/   CRUD, versions, snapshots                  │
│    label/     LS-JSON validate, region ops               │
│    llm/       planner · prelabel · judge · advisor       │
│               (pydantic structured-output, Ollama HTTP)  │
│    inspect_service/  HTTP client → auto-inspect-service  │
│    deploy/    promote, version pin, edge notification    │
│  db/          PostgreSQL: projects, bom_items, labels,   │
│               train_runs, deployments, eval_metrics      │
│  storage/     fs: {project_id}/{kind}/{file}             │
└──┬────────────────────────┬───────────────────────┬──────┘
   │                        │                        │
   │ HTTP                   │ HTTP                   │ HTTP
   ▼                        ▼                        ▼
┌─────────────┐   ┌──────────────────┐   ┌───────────────────┐
│ Ollama      │   │ auto-inspect-    │   │ auto-inspect-edge │
│ gemma4:31b  │   │ service (existing│   │ (existing,        │
│ (dedicated  │   │ FastAPI :8001)   │   │ optional VLM      │
│ GPU box)    │   │ — train, infer,  │   │ judge call to     │
│             │   │ model registry   │   │ Ollama for        │
│             │   │ Git+LFS          │   │ borderline ROI)   │
└─────────────┘   └──────────────────┘   └───────────────────┘
```

### 4. End-to-end user journey (revised per decision #12)

```
MI division operator/supervisor:
  1. Create project "NV80-017542-0501" (PCB model code from customer)
  2. Upload BOM.xlsx → preview parsed (~200 items, MI/SMT badged)
  3. Upload golden_top.jpg + golden_bottom.jpg + (opsional) drawing.png
  4. Open Labeling Canvas:
       a. Gemma 4 has auto-pre-labeled ALL BOM designators (bbox + class)
          using golden+drawing as priors. Predictions[] populated in LSF task.
       b. User reviews bbox accuracy + class assignment, corrects where needed.
          High-confidence (≥0.85) regions green, low (<0.6) yellow flagged.
       c. For each region user decides:
            • inspect_scope = "inspected" or "skipped"  (required, default=skipped)
            • if inspected: defect_criteria = multi-select from
                missing_component, orientation, polarity_flip,
                connector_pin_bending, missing_pin_connector,
                lifted_pin, wrong_value, misalignment, solder_short, ...
       d. Skipped regions dim on canvas (visual coverage map)
       e. Save → backend derives bom_items.inspect_scope + detector_presets
  5. Click "🤖 Build inspection pipeline" → Gemma planner reads scope+criteria
     from canvas-derived state, generates graphflow DAG, writes to auto-inspect-service
  6. ★ GATE 1: "Start training?" — review preview dataset + auto-suggested
     epochs/augmentation → Approve
  7. Training in auto-inspect-service (SSE progress)
  8. Eval metrics page (mAP, F1 PER-COMPONENT — not just global) + sample preds
  9. ★ GATE 2: "Promote to production?" → Approve
 10. visual-editor pushes weights to registry, notifies edges → auto-pull
 11. Inspection runs on MI line; only inspected components evaluated per criteria
 12. (Optional) Chat advisor: "C4 false-positive 5% di line 3, kenapa?"
```

Key shift from earlier draft: scope+criteria decisions move from a separate wizard step into the labeling canvas itself (single mental model). Planner runs AFTER labeling (not before), so it has authoritative scope+criteria to seed the DAG.

### 5. Component breakdown

#### 5.1 Frontend (`web/`, Vue 3 + Vite)

```
src/
├── views/
│   ├── Dashboard.vue           projects list, status badges
│   ├── ProjectWizard.vue       3-step setup (BOM, assets, plan)
│   ├── LabelingCanvas.vue      Konva.js stage + tools
│   ├── TrainEval.vue           SSE metrics, sample preds, promote button
│   └── DeployMonitor.vue       edge list, version history, rollback
├── components/
│   ├── CanvasToolbar.vue       bbox tool, polygon, AI pre-label trigger
│   ├── RegionList.vue          right panel, confidence colors
│   ├── BomTable.vue            parsed BOM with edit
│   ├── PipelineProposal.vue    Gemma DAG output review
│   └── ChatDrawer.vue          advisor chat panel (slide-out)
├── stores/  (Pinia)
│   ├── projects.ts
│   ├── labels.ts
│   └── training.ts
├── api/                        thin axios wrappers
└── canvas/                     Konva.js wrappers, region serialization
```

LS-JSON schema reference: https://labelstud.io/guide/predictions.html (RectangleLabels + Choices). Internal canvas state ↔ LS-JSON adapter in `canvas/ls-format.ts`.

#### 5.2 Backend (`src/indusia_visual_editor/`, FastAPI)

```
src/indusia_visual_editor/
├── main.py                FastAPI app + lifespan + middleware
├── config.py              pydantic-settings (IVE_ prefix env vars)
├── routes/
│   ├── projects.py
│   ├── assets.py          upload BOM/golden/drawing
│   ├── labels.py          GET/PUT label JSON, pre-label trigger
│   ├── training.py        start (GATE 1), status, eval
│   ├── deploy.py          promote (GATE 2), rollback
│   ├── chat.py            advisor SSE
│   └── webhooks.py        from auto-inspect-service train events
├── services/
│   ├── asset/
│   │   ├── bom_parser.py        openpyxl/pandas → typed rows
│   │   ├── image_store.py       fs save + thumbnail
│   │   └── drawing_proc.py      JPG/PNG normalize
│   ├── project/
│   │   ├── crud.py
│   │   └── versioning.py        label snapshot per training run
│   ├── label/
│   │   ├── ls_format.py         in/out validator (pydantic)
│   │   └── region_ops.py        merge/split/copy ops
│   ├── llm/
│   │   ├── client.py            Ollama HTTP client (httpx async)
│   │   ├── schemas.py           pydantic models for structured output
│   │   ├── planner.py           BOM + golden → ProposedPipeline schema
│   │   ├── prelabel.py          golden + BOM → list[Region]
│   │   ├── judge.py             ROI crop → DefectVerdict (called by edge)
│   │   └── advisor.py           chat with project context
│   ├── inspect_service/
│   │   ├── client.py            httpx → auto-inspect-service :8001
│   │   └── adapters.py          ProposedPipeline → config.yaml format
│   └── deploy/
│       ├── promote.py           wrap `ais model add/commit/push` via subprocess OR REST
│       └── notify.py            optional webhook → edges
├── db/
│   ├── models.py                SQLAlchemy
│   ├── session.py
│   └── alembic/                 migrations
└── utils/
    ├── logging_config.py
    └── responses.py             {status, message, data} shape — MATCH existing services
```

#### 5.3 Database schema (Postgres)

```sql
projects          id, name, slug, status, created_at, updated_at
bom_items         id, project_id, designator, value, package, qty, position_hint,
                  -- inspect-scope fields (user-controlled in canvas)
                  inspect_scope ENUM('pending', 'inspected', 'skipped'),  -- default 'pending' until canvas annotation
                  mi_likely BOOL,                  -- HEURISTIC HINT ONLY (badge color, sort, smart-select). Not a scope decision.
                  component_type VARCHAR(64),      -- 'electrolytic_cap'|'dip_ic'|'connector'|'tht_resistor'|... (Gemma-tagged)
                  defect_history_count INT DEFAULT 0  -- optional: imported from prior defect logs
assets            id, project_id, kind ('bom'|'golden_top'|'golden_bottom'|'drawing'), path, sha256
proposed_pipelines  id, project_id, version, dag_json, approved_by, approved_at
                  -- dag_json only covers bom_items WHERE inspect_scope='inspected'
labels            id, project_id, version, side, ls_json, snapshot_at
train_runs        id, project_id, label_version, service_job_id, status, metrics_json, started_at, ended_at
                  -- metrics_json includes per-component F1 (not just global)
deployments       id, project_id, train_run_id, model_version, edges_notified, deployed_at
chat_sessions     id, project_id, messages_json, created_at
```

**inspect_scope semantics (revised — user-controlled in canvas, not auto-set):**
- `pending` (default after BOM upload) — Gemma will auto-pre-label, user belum putuskan inspect/skip
- `inspected` — user opted in via canvas `<Choices perRegion>`; goes into planner + training class list
- `skipped` — user opted out via canvas; dim in canvas UI, excluded from training

**`mi_likely` is independent hint** (not a scope state) — visual badge in canvas + smart-select shortcuts, never auto-decides scope.

#### 5.4 LLM structured-output contracts

Use Ollama `format: json` mode + pydantic validation.

```python
class ProposedPipelineStep(BaseModel):
    designator: str         # "C4"
    component_type: str     # "electrolytic_capacitor"
    detectors: list[Literal["yolo", "anomalib", "ocr", "barcode", "template_match"]]
    reasoning: str

class ProposedPipeline(BaseModel):
    pcb_model: str
    fiducial_strategy: Literal["circle", "orb", "yolo", "threshold"]
    steps: list[ProposedPipelineStep]

class PreLabeledRegion(BaseModel):
    designator: str
    bbox: tuple[float, float, float, float]  # x, y, w, h (normalized 0-1)
    confidence: float
    side: Literal["top", "bottom"]

class DefectVerdict(BaseModel):
    verdict: Literal["pass", "fail", "uncertain"]
    confidence: float
    reason_short: str        # for log
    reason_detail: str       # for UI hover
```

### 6. Data Integration Map

| Component | Data Source | Existing? | Notes |
|---|---|---|---|
| Project CRUD | new PG `projects` table | NO | new schema |
| BOM parser | upload → openpyxl/pandas → `bom_items` | NO | greenfield |
| Asset storage | filesystem `storage/{project_id}/{kind}/` | NO | fs v1, S3/MinIO v2 |
| Label JSON | `labels` table + fs snapshot | NO | LS-JSON format spec |
| LLM planner → graphflow config | Gemma 4 structured output → POST `auto-inspect-service /api/setup/...` | PARTIAL | service has setup flow; adapter needed |
| Pre-label predictions | Gemma 4 + (optional) `YoloEstimator` for known classes | PARTIAL | engine accessible via service |
| Training trigger | POST `auto-inspect-service /api/training/start` | YES | existing `training_service.py` + SSE |
| Eval metrics + sample preds | SSE from training run + sample inference endpoint | YES | existing |
| Promote-to-production | `ais model push` via REST OR subprocess wrap | PARTIAL | CLI exists; REST endpoint TBD |
| Edge auto-pull notification | webhook / poll → edge runs `ais model pull` | PARTIAL | mechanism exists; needs orchestration |
| Runtime VLM judge | edge → Ollama HTTP | NO | requires `auto-inspect-edge` modification |
| Chat advisor | Gemma 4 + project history query | NO | greenfield |

### 7. Implementation feasibility flags

- ⚠️ **Promote-to-production via REST** not yet exposed by `auto-inspect-service`. Options: (a) add new REST endpoint to service (preferred, ~1 day work), (b) shell-out to `ais model` CLI from visual-editor (works but coupling). Decide in plan phase.
- ⚠️ **Adapter `ProposedPipeline → config.yaml graphflow DAG`**: needs schema verification against actual `auto-inspect-service` config.yaml format (`prod/configs/pcb_1/`). Spike before plan finalize.
- ⚠️ **Runtime VLM judge** modifies `auto-inspect-edge` — explicitly outside MVP scope in user's earlier answer, but the brainstorm included it as VLM role. Recommend: ship judge as optional **v1.5** after main loop is stable. Document the integration point but don't build in v1.
- ⚠️ **Gemma 4 31b real-world inference time** for pipeline planner with full BOM + golden sample image (multi-MB) on dedicated GPU = ~5–30s estimated. Acceptable for offline. Budget UI loading state accordingly. [Assumption — benchmark during plan spike]
- ⚠️ **Label JSON storage**: large PCBs may have 300+ regions × 2 sides = 600 LS-JSON regions. Test query/diff/snapshot performance early.

### 8. Stack summary

| Layer | Choice | Why |
|---|---|---|
| Frontend | Vue 3 + Vite + TypeScript + Pinia + Konva.js + Tailwind | matches Ali's tech-preferences |
| Backend | FastAPI + pydantic-settings + SQLAlchemy 2 + Alembic + httpx (async) + sse-starlette | matches existing services for consistency |
| DB | PostgreSQL 16 | per global stack pref |
| Storage | local filesystem v1; S3/MinIO upgrade later | YAGNI for MVP |
| LLM | Ollama gemma4:31b on dedicated GPU box | locked above |
| Auth | basic email/password + JWT for MVP; consider Supabase Auth v2 | minimum to demo |
| Container | Docker Compose | per global stack pref |
| Reverse proxy | Traefik (auto HTTPS) | per global stack pref |
| Code style | black + isort + flake8 (Python); eslint + prettier (Vue) | match existing repos |

### 9. Out of scope (MVP)

- New HMI inspection screen (use existing edge UI)
- Runtime VLM judge in edge (defer to v1.5)
- Multi-tenant / org management (single tenant v1)
- Audit log + RBAC (basic user only)
- Gerber / ODB++ CAD import (Excel BOM + image-only drawing v1)
- BOM via PDF/OCR (only Excel/CSV v1)
- Mobile responsive (desktop-first; canvas requires keyboard+mouse)
- Real-time multi-user collaboration on canvas (single-editor lock)
- Localization (English UI v1)

### 10. Open questions to resolve in `gaspol-plan`

1. Auth: simple JWT vs Supabase Auth from day 1?
2. REST vs subprocess for `ais model push` orchestration?
3. Snapshot label JSON to filesystem on every save, or only at training trigger?
4. Konva.js performance budget — at what region count do we need virtualization?
5. Project naming convention vs existing `prod/configs/{pcb_id}/` — slugify rules?
6. Webhook security — how do we authenticate edge → visual-editor and visual-editor → edge?

---

## Implementation Plan

> **For Claude:** REQUIRED SKILL: Use `gaspol-execute` to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution, NEVER substitute placeholders for real data sources without explicit user approval. If a data source doesn't exist yet, STOP and ask.
>
> **Plan scope:** Detailed phases for M0–M3 (foundation, executable now). M4–M14 listed as roadmap; re-invoke `gaspol-plan` after M3 ships to detail next milestones.

### Goal

Ship a Vue 3 + FastAPI platform (`indusia-visual-editor`) that lets a manufacturing engineer take a brand-new PCB from photo to production inspection in hours via: upload BOM + golden sample → Gemma 4 auto-plans pipeline + pre-labels → human review on Konva canvas → 2-gate approval → training in existing `auto-inspect-service` → push weights to existing Git+LFS registry → existing `auto-inspect-edge` pulls and runs. Zero YAML editing, zero CLI use by the factory user.

### Architecture Context (from CLAUDE.md files)

**Existing services to integrate with (DO NOT modify in v1):**
- `auto-inspect-service` (FastAPI :8001) — discover models, `POST /api/models/{name}/load`, `POST /api/training/start` + SSE, Git+LFS registry via `ais model push/pull`. Models live in `prod/configs/{pcb_id}/` with `config.yaml` (graphflow DAG) + `locations.yaml` + `settings.yaml` + `components/*.yaml` + `assets/`. Response shape `{status, message, data}` via `success()/failed()` helpers.
- `auto-inspect-engine` — `BaseEstimator` foundation, **RGB images everywhere**, YOLO via Ultralytics + Anomalib (OpenVINO) + fiducial + OCR + barcode + template matching. Iron Law: model classes extend `BaseEstimator`/`BaseTransform`.
- `auto-inspect-edge` (FastAPI :8000) — PLC + Hikrobot orchestrator, pulls weights via `ais model pull`. Receives selected model from cache (`.cache/selected_model.json`). **Unchanged in v1.**

**Existing config.yaml graphflow format example** (verify in spike at Phase 0.2): node DAG with `type:`, `params:`, `edges:`; subgraph YAMLs in `components/`; `name:` field = API identifier (URL-safe slug).

**Conventions to match:**
- Windows paths in code (project runs on Windows + Linux servers)
- Python 3.10+, FastAPI + pydantic-settings, env prefix this service uses: `IVE_`
- Response shape `{status: bool, message: str, data: ...}` (match service)
- Logging via `logging.getLogger(__name__)`
- Anti-AI-slop: no emojis in code/UI strings unless user asks
- Bahasa Indonesia default in UI strings + commit messages, technical terms English

### Tech Stack (locked)

| Layer | Choice |
|---|---|
| Backend lang | Python 3.10+ |
| Web framework | FastAPI 0.121+ + uvicorn |
| Config | pydantic-settings (`IVE_` prefix) |
| HTTP client | httpx (async) — different from existing services' `requests` (sync) — appropriate for async FastAPI |
| ORM | SQLAlchemy 2.x + Alembic |
| DB | PostgreSQL 16 (Docker Compose) |
| SSE | sse-starlette |
| Image I/O | opencv-python + PyTurboJPEG (match engine) |
| LLM client | httpx direct to Ollama HTTP API (`/api/generate` + `/api/chat`) |
| Tests | pytest + pytest-asyncio + factory-boy + httpx AsyncClient |
| Packaging | Poetry (match existing services) |
| Frontend | Vue 3 + Vite + TS + Pinia + Vue Router |
| Canvas | Konva.js (`konva-vue` wrapper or direct) |
| HTTP (FE) | axios + EventSource (SSE) |
| Styling | Tailwind CSS 3 |
| Frontend tests | Vitest + @vue/test-utils |
| Container | Docker Compose (dev + prod) |
| Reverse proxy (prod) | Traefik |
| Code style | black + isort + flake8 (Python); eslint + prettier (Vue) |

### Data Integration Map (extended for execution)

| Feature | Data Source | Module / Hook / API | Exists? | Action |
|---|---|---|---|---|
| Project CRUD | new PG `projects` table | `routes/projects.py` + `services/project/crud.py` | No | Create new |
| BOM parse + store | upload → openpyxl/pandas → `bom_items` | `services/asset/bom_parser.py` | No | Create new |
| Asset blob storage | filesystem `storage/{project_id}/{kind}/` | `services/asset/image_store.py` | No | Create new |
| Label JSON | `labels` table + fs snapshot | `services/label/ls_format.py` | No | Create new |
| Pipeline planner | Ollama `gemma4:31b` + pydantic structured output | `services/llm/planner.py` | No | Create new |
| Pre-label predictions | Ollama VLM + golden image | `services/llm/prelabel.py` | No | Create new |
| Defect judge (v1.5) | Ollama VLM + ROI crop | `services/llm/judge.py` | No | **Defer to v1.5** |
| Chat advisor | Ollama + project history | `services/llm/advisor.py` | No | Create new (M12) |
| Training trigger | `auto-inspect-service /api/training/start` | `services/inspect_service/client.py` | YES (in service) | Wrap via httpx |
| Eval metrics SSE | service training SSE stream | same client | YES | Subscribe + relay |
| Promote-to-production | `ais model push` (subprocess wrap OR new REST endpoint) | `services/deploy/promote.py` | PARTIAL | See Phase decision in M10 |
| Edge notification | webhook to edge `/api/models/refresh` (or poll) | `services/deploy/notify.py` | PARTIAL | Spike in M11 |
| Konva canvas state | LS-JSON in/out | `web/src/canvas/ls-format.ts` | No | Create new |
| Auth | JWT email/password (basic) | `routes/auth.py` + middleware | No | Create new (M13) |

### Milestone roadmap

| Milestone | Title | Detailed below? | Est. days |
|---|---|---|---|
| **M0** | Bootstrap (monorepo, FastAPI hello, Vue scaffold, docker-compose) | ✅ Yes | 1 |
| **M1** | Project + Asset CRUD + Dashboard UI | ✅ Yes | 2 |
| **M2** | BOM parser + MI/SMT classifier (for default visual hints) + defect-criteria taxonomy + preview table | ✅ Yes | 1.5 |
| **M3** | LLM client foundation (Ollama wrapper + pydantic schemas + planner stub) | ✅ Yes | 2 |
| M4 | Pipeline planner: **(inspected subset of BOM) + Golden + Drawing** → graphflow config.yaml with **MI-detector presets** (lifted_pin, border_alignment, polarization, OCR per component_type) → write to service | Roadmap | 3 |
| M5 | Pre-label assistant (Gemma + Yolo fallback) | Roadmap | 2 |
| M6 | Labeling canvas (Konva + LS-JSON) | Roadmap | 4 |
| M7 | Training integration (call service + SSE relay) | Roadmap | 2 |
| M8 | Gate 1 UI (approve before training) | Roadmap | 1 |
| M9 | Eval metrics view + sample preds | Roadmap | 2 |
| M10 | Gate 2 + promote-to-production | Roadmap | 2 |
| M11 | Edge notification + version pin | Roadmap | 2 |
| M12 | Chat advisor | Roadmap | 2 |
| M13 | Auth + multi-user basics | Roadmap | 2 |
| M14 | Polish + deploy + docs | Roadmap | 3 |
| **Total** | | | **~31 days solo (~6 weeks)** |

---

## M0 — Bootstrap

### Phase 0.1: Backend project scaffold

**Estimated time:** 12 min
**Files:**
- Create: `pyproject.toml`, `README.md`, `.gitignore`, `.env.example`
- Create: `src/indusia_visual_editor/__init__.py`, `src/indusia_visual_editor/main.py`, `src/indusia_visual_editor/config.py`
- Test: `tests/test_health.py`

**Steps:**
1. Write failing test `tests/test_health.py::test_health_endpoint_returns_status_ok` using httpx AsyncClient against `app`. Expected error: `ModuleNotFoundError: No module named 'indusia_visual_editor'`.
2. Run `poetry run pytest tests/test_health.py -v` — confirm fail for expected reason
3. Run `poetry init` (or write `pyproject.toml` by hand) with deps: fastapi, uvicorn[standard], pydantic-settings, httpx, sse-starlette, pytest, pytest-asyncio
4. Create `src/indusia_visual_editor/config.py` with `AppConfig(BaseSettings)` env prefix `IVE_`, fields: `app_host`, `app_port`, `log_level`
5. Create `src/indusia_visual_editor/main.py`: FastAPI app, `GET /health` returns `{"status": True, "message": "ok", "data": {"version": "0.1.0"}}` matching existing service shape
6. Run tests — confirm pass
7. Commit: `feat(bootstrap): initial FastAPI scaffold with /health endpoint`

**Verification:**
- [ ] `poetry install` succeeds
- [ ] `poetry run pytest -v` 1 test passes
- [ ] `poetry run uvicorn indusia_visual_editor.main:app --reload` boots without error, `GET /health` returns 200 with the expected shape
- [ ] No placeholder/TODO comments in new code

### Phase 0.2: Spike — verify `auto-inspect-service` config.yaml schema

**Estimated time:** 15 min
**Files:**
- Read: `D:\Projects\Indusia-Inspection\auto-inspect-service\prod\configs\` (or `configs/`) for an example PCB
- Create: `docs/specs/graphflow-config-schema.md` (notes only)

**Steps:**
1. Write failing test `tests/spike/test_graphflow_schema.py::test_can_parse_example_config_yaml` that loads an existing `config.yaml` from `Indusia-Inspection` and asserts top-level keys (`name`, `nodes`, `edges`). Expected error: `FileNotFoundError` or `KeyError` — confirm the actual schema first.
2. Run, see fail
3. Inspect 1–2 real config.yamls; document observed top-level structure + node `type:` registry strings in `docs/specs/graphflow-config-schema.md`
4. Update test to assert observed keys; run, see pass
5. Commit: `docs(spike): document graphflow config.yaml schema for planner adapter`

**Verification:**
- [ ] `docs/specs/graphflow-config-schema.md` exists with: top-level fields list, ≥3 example node `type:` strings, locations.yaml structure
- [ ] Spike test passes
- [ ] Open question logged: which node types should Gemma planner emit in M4?

### Phase 0.3: Frontend scaffold

**Estimated time:** 12 min
**Design Deliverable:** **n/a** (scaffold-only; tokens deferred to Phase 1.5 via `gaspol-design`)
**Files:**
- Create: `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/index.html`
- Create: `web/src/main.ts`, `web/src/App.vue`, `web/src/router/index.ts`, `web/src/views/Dashboard.vue` (stub)
- Test: `web/src/__tests__/App.spec.ts`

**Steps:**
1. Write failing Vitest test `web/src/__tests__/App.spec.ts::App renders router-view`. Expected error: `Cannot find module './App.vue'`.
2. Run `pnpm test` — see fail
3. `pnpm create vite web -- --template vue-ts` (or hand-write minimal) + add deps: vue-router@4, pinia, axios, tailwindcss, konva
4. Implement `App.vue` with `<router-view />`, Router with 1 route `/` → `Dashboard.vue` showing "Visual Editor" heading
5. Run tests, confirm pass
6. Commit: `feat(web): Vue 3 + Vite scaffold with router, Pinia, Tailwind, Konva`

**Verification:**
- [ ] `pnpm dev` boots, browsing `http://localhost:5173` shows "Visual Editor"
- [ ] `pnpm test` 1 test passes
- [ ] `pnpm build` succeeds (tsc passes)
- [ ] No placeholder/TODO in new code

### Phase 0.4: Docker Compose dev environment

**Estimated time:** 10 min
**Files:**
- Create: `docker-compose.dev.yml`, `Dockerfile.api`, `web/Dockerfile`
- Create: `scripts/dev-up.ps1`, `scripts/dev-down.ps1`

**Steps:**
1. Write failing test `tests/test_db_connection.py::test_can_connect_to_postgres` (uses asyncpg, expects env `IVE_DATABASE_URL`). Expected: `ModuleNotFoundError: asyncpg` or connection refused
2. Run, see fail
3. Add `asyncpg`, `sqlalchemy[asyncio]` to deps
4. Author `docker-compose.dev.yml` with services: `postgres:16-alpine` (port 5432), `api` (mount `src/`), `web` (mount `web/`). Health check on postgres.
5. Write `.env.example` with `IVE_DATABASE_URL=postgresql+asyncpg://ive:ive@localhost:5432/ive`
6. Run `docker compose -f docker-compose.dev.yml up -d postgres`; run db test; confirm pass
7. Commit: `feat(dev): Docker Compose with Postgres + API + Web services`

**Verification:**
- [ ] `docker compose -f docker-compose.dev.yml up postgres -d` brings DB up
- [ ] `poetry run pytest tests/test_db_connection.py -v` passes against the running container
- [ ] `scripts/dev-up.ps1` is a working one-liner
- [ ] Compose file uses named volumes, no hardcoded paths

---

## M1 — Project + Asset CRUD + Dashboard

### Phase 1.1: DB schema + Alembic baseline (projects, assets, bom_items)

**Estimated time:** 15 min
**Files:**
- Create: `src/indusia_visual_editor/db/__init__.py`, `db/session.py`, `db/models.py`
- Create: `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py`
- Test: `tests/test_db_models.py`

**Steps:**
1. Write failing test `tests/test_db_models.py::test_project_can_be_created_and_queried` (uses test session, creates Project + Asset). Expected: `ModuleNotFoundError: No module named '...db.models'`.
2. Run, see fail
3. Implement `db/session.py` (async engine + `get_session` dependency from env `IVE_DATABASE_URL`)
4. Implement `db/models.py`: `Project`, `Asset`, `BomItem` matching schema section §5.3 of design. UUID PKs, timezone-aware timestamps, FKs.
5. Run `alembic init alembic` and write `0001_initial.py` (or autogenerate)
6. Run `alembic upgrade head` against the dev DB; run tests; confirm pass
7. Commit: `feat(db): initial schema for projects, assets, bom_items`

**Verification:**
- [ ] `alembic upgrade head` succeeds on empty DB
- [ ] `alembic downgrade base` then `upgrade head` cleanly re-applies
- [ ] Test passes — Project + Asset roundtrip via async session
- [ ] No raw SQL strings outside Alembic migrations

### Phase 1.2: Projects CRUD routes

**Estimated time:** 15 min
**Files:**
- Create: `src/indusia_visual_editor/routes/projects.py`, `schemas/projects.py`, `services/project/crud.py`
- Modify: `main.py` (wire router)
- Test: `tests/routes/test_projects.py`

**Steps:**
1. Write failing tests in `tests/routes/test_projects.py`: `test_create_project`, `test_list_projects`, `test_get_project`, `test_update_project`, `test_delete_project` using httpx AsyncClient against the FastAPI test app. Expected: `404 Not Found` on all routes.
2. Run, see fail
3. Implement pydantic schemas in `schemas/projects.py` (`ProjectCreate`, `ProjectRead`, `ProjectUpdate`)
4. Implement `services/project/crud.py` with async functions: `create_project`, `list_projects`, `get_project`, `update_project`, `delete_project`
5. Implement `routes/projects.py` with `APIRouter(prefix="/api/projects")` and 5 endpoints returning `{status, message, data}` shape
6. Wire router in `main.py`; run tests; confirm all pass
7. Commit: `feat(api): projects CRUD endpoints with async session`

**Verification:**
- [ ] All 5 endpoint tests pass
- [ ] Response shape matches `{status, message, data}` on success AND error paths (test 404 explicitly)
- [ ] Slug uniqueness enforced (DB constraint + 409 Conflict on duplicate)
- [ ] No raw SQL outside migrations
- [ ] OpenAPI docs at `/docs` render the new routes

### Phase 1.3: Asset upload endpoint + filesystem storage

**Estimated time:** 12 min
**Files:**
- Create: `src/indusia_visual_editor/routes/assets.py`, `schemas/assets.py`, `services/asset/image_store.py`
- Test: `tests/routes/test_assets.py`

**Steps:**
1. Write failing test `tests/routes/test_assets.py::test_upload_golden_top_image` — multipart POST to `/api/projects/{id}/assets?kind=golden_top` with small PNG. Expected: 404.
2. Run, see fail
3. Implement `services/asset/image_store.py`: `save_asset(project_id, kind, file_bytes, filename) -> Asset` — writes to `storage/{project_id}/{kind}/{sha256}.{ext}`, computes sha256, inserts row
4. Implement `routes/assets.py` with POST + GET (list) + GET-binary (serve file) endpoints. `kind` validation via Literal type.
5. Run tests, confirm pass. Add test for rejecting wrong kind + oversized file (>50MB cap from config).
6. Commit: `feat(assets): upload + serve assets per project with sha256 dedup`

**Verification:**
- [ ] Upload writes file to `storage/{project_id}/{kind}/`
- [ ] Returned Asset row has correct sha256, mime detected
- [ ] Re-uploading identical content returns existing Asset row (dedup by sha256, no duplicate row)
- [ ] Wrong `kind` returns 422; >50MB returns 413
- [ ] No file path traversal (test with `../` filename)

### Phase 1.4: Frontend Dashboard view (list + create project)

**Estimated time:** 15 min
**Design Deliverable:** Tokens + layout for Dashboard via `gaspol-design` (industrial dark theme, mono font for IDs, dense tabular). See `docs/design/dashboard-tokens.md`.
**Files:**
- Modify: `web/src/views/Dashboard.vue`
- Create: `web/src/stores/projects.ts`, `web/src/api/projects.ts`, `web/src/components/ProjectCreateDialog.vue`
- Test: `web/src/__tests__/Dashboard.spec.ts`

**Steps:**
1. Invoke `gaspol-design` for Dashboard: deliver `docs/design/dashboard-tokens.md` with color tokens, font scale, spacing, table density, status badge variants (drafting/training/deployed/failed)
2. Write failing test `Dashboard.spec.ts::renders project list from store + shows New Project button`. Expected: list count `0`, button missing.
3. Implement `api/projects.ts` axios client (GET /list, POST /create)
4. Implement `stores/projects.ts` (Pinia) with `state: { items, loading, error }` + `actions: fetch(), create(payload)`
5. Implement `Dashboard.vue`: header "Projects" + button "New Project" opens `ProjectCreateDialog`, table of projects with columns (Name, Status, Updated). Empty state copy: "Belum ada project. Mulai dengan upload BOM dan Golden Sample."
6. Implement `ProjectCreateDialog.vue` with form (name, slug auto-derived) → POST → redirect to `/projects/:id/wizard`
7. Run tests, confirm pass
8. Commit: `feat(web): Dashboard view with project list and create dialog`

**Verification:**
- [ ] Vitest test passes
- [ ] Manual smoke: open `pnpm dev`, see Dashboard, create project, see it appear in list, click → navigate to wizard route (404 ok, wizard built in Phase 2.x)
- [ ] Tokens from `docs/design/dashboard-tokens.md` applied (no random Tailwind classes)
- [ ] Empty state Bahasa Indonesia, no AI slop phrasing
- [ ] No hardcoded color hex outside tokens config

---

## M2 — BOM Parser + Preview

### Phase 2.1: BOM parser service (Excel + CSV)

**Estimated time:** 15 min
**Files:**
- Create: `src/indusia_visual_editor/services/asset/bom_parser.py`
- Create: `tests/fixtures/sample_bom.xlsx`, `tests/fixtures/sample_bom.csv`
- Test: `tests/services/test_bom_parser.py`

**Steps:**
1. Write failing tests: `test_parse_xlsx_extracts_designators`, `test_parse_csv_extracts_designators`, `test_rejects_missing_designator_column`, `test_handles_comma_separated_multi_designator_rows`. Expected: `ImportError` or `AttributeError`.
2. Run, see fail
3. Implement `BomItem` pydantic model + `parse_bom(file_bytes, filename) -> list[BomItem]` using openpyxl for xlsx, csv stdlib for csv
4. Handle the common BOM convention: rows with `Designator: "R1, R2, R3"` expand to 3 BomItem rows sharing value/package
5. Column detection: lowercased fuzzy match for `designator|reference|ref|comp`, `value|val`, `package|footprint|fp`, `qty|quantity`
6. Run tests, confirm pass
7. Commit: `feat(bom): parse Excel and CSV BOM with multi-designator row expansion`

**Verification:**
- [ ] All 4 tests pass
- [ ] Parser tolerates header in row 1, 2, or 3 (tests cover row-2 header)
- [ ] Missing required column raises `BomParseError` with clear message in Bahasa Indonesia
- [ ] No silent data loss — extra columns logged + preserved as `extra: dict`

### Phase 2.2: BOM upload route + DB persistence

**Estimated time:** 10 min
**Files:**
- Modify: `routes/assets.py` (add `kind="bom"` special handling)
- Modify: `services/asset/image_store.py` (route bom kind to bom_parser)
- Test: `tests/routes/test_assets.py` (add bom case)

**Steps:**
1. Write failing test `test_upload_bom_persists_bom_items`. Expected: 0 bom_items rows after upload.
2. Run, see fail
3. In asset upload handler, when `kind=="bom"`: save file (existing flow) AND call `parse_bom()` → bulk insert `BomItem` rows linked to project
4. Wrap in single transaction — if parse fails, rollback (no orphan Asset row)
5. Run tests, confirm pass
6. Commit: `feat(bom): persist parsed BOM items on upload, transactional`

**Verification:**
- [ ] Test passes — bom_items count > 0 after upload, linked to project_id
- [ ] Bad BOM file (test with binary garbage as .xlsx) returns 422 + no DB rows
- [ ] Re-uploading replaces old BOM items (test explicit) OR appends (decide + document)
- [ ] OpenAPI docs reflect bom-specific response shape

### Phase 2.2b: MI-vs-SMT heuristic classifier (per §1.5)

**Estimated time:** 12 min
**Files:**
- Create: `services/asset/mi_classifier.py`, `data/component_taxonomy.yaml`
- Modify: `services/asset/bom_parser.py` (call classifier after parse)
- Test: `tests/services/test_mi_classifier.py`

**Steps:**
1. Write failing test `test_classifier_marks_smd_packages_as_auto_smt`, `test_classifier_marks_through_hole_as_mi_likely`, `test_classifier_handles_unknown_package_as_mi_likely_for_safety`. Expected: `ImportError`.
2. Run, see fail.
3. Author `data/component_taxonomy.yaml` with two regex lists:
   - `smd_patterns`: `0201|0402|0603|0805|1206|1210|2010|2512|SOT-?\d+|SOIC-?\d+|TSSOP|QFN|QFP|BGA|LGA|MLF|DFN|WLCSP|SMA|SMB|SMC|0\\d{3}-?[a-z]+`
   - `tht_patterns`: `DIP-?\d+|PDIP|SIP|ZIP|TO-?\d+|Radial|Axial|HDR|HEADER|PIN|TERM|JUMPER|TRANSFO|RELAY|XTAL.*TH|FUSE.*TH`
4. Implement `classify(package: str, value: str = "", designator: str = "") -> ClassifyResult` with fields `mi_likely`, `component_type`. This is a **HINT only** — does NOT set `inspect_scope` directly (scope decided by user per-region in canvas). Rules:
   - Match `smd_patterns` (case-insensitive) → `mi_likely=False`, `component_type='smd_generic'` or more specific
   - Match `tht_patterns` → `mi_likely=True`, `component_type='tht_generic'` or specific (electrolytic_cap, dip_ic, connector, etc.)
   - Designator prefix `CN/J/JP/X/SW/T/L/RV/D/U+DIP` and unknown package → `mi_likely=True`
   - Otherwise → default `mi_likely=False` (canvas UI shows as "unclassified", user override OK)
5. Update `bom_parser.parse_bom` to set `mi_likely`/`inspect_scope`/`component_type` on each `BomItem`.
6. Add tests for ambiguous cases (e.g., package=`""`, designator=`U7`, value=`STM32F4` → expect mi_likely=False because most ICs are SMD now).
7. Commit: `feat(bom): MI vs SMT package-based heuristic classifier`

**Verification:**
- [ ] All classifier tests pass
- [ ] BOM parse on `sample_bom.xlsx` (fixture) populates new fields correctly
- [ ] `data/component_taxonomy.yaml` editable without code change (user can extend)
- [ ] Classifier is pure function (no DB / external calls) — fast + cacheable

### ~~Phase 2.2c: Component-selector wizard step~~ — REMOVED

> **Removed per decision #12** (unified canvas UX). Scope is now picked per-region inside the labeling canvas via `<Choices perRegion>`, not via a separate wizard step. The MI/SMT heuristic from Phase 2.2b still runs to set default visual hints (skipped/inspected default state per region), but no separate UI step.

### Phase 2.2c (replacement): Defect detector mapping + criteria taxonomy

**Estimated time:** 10 min
**Files:**
- Create: `data/defect_detector_mapping.yaml`, `data/component_taxonomy.yaml` (extend from 2.2b)
- Create: `services/inspect_scope/derive.py`
- Test: `tests/services/test_derive_inspect_scope.py`

**Steps:**
1. Write failing test `test_derive_inspect_scope_from_lsf_annotation` — given an LS-JSON annotation with `inspect_scope=inspected` + `defect_criteria=[missing_component, polarity_flip]` for region "C4", expect `bom_items[C4].inspect_scope='inspected'` AND `bom_items[C4].detector_presets=['yolo', 'orientation_classifier', 'polarity_template']`. Expected: `ImportError`.
2. Run, see fail.
3. Author `data/defect_detector_mapping.yaml`:
   ```yaml
   missing_component:     [yolo]
   orientation:           [yolo, orientation_classifier]
   polarity_flip:         [yolo, orientation_classifier, polarity_template]
   connector_pin_bending: [yolo, anomalib_roi, lifted_pin]
   missing_pin_connector: [yolo_fine_grained, pin_count_check]
   lifted_pin:            [lifted_pin]
   wrong_value:           [yolo, ocr]
   misalignment:          [border_alignment, anomalib_roi]
   solder_short:          [anomalib_whole_side, threshold]   # only for whole_side scope mode
   ```
4. Implement `derive_inspect_scope(annotation: LSAnnotation, project_id: UUID) -> list[BomItemUpdate]`:
   - Group `result[]` entries by region `id` (rectanglelabels + 2 choices share id)
   - For each region: lookup designator + scope + criteria → emit BomItemUpdate
   - For criteria → detectors: apply yaml lookup, union sets across criteria
5. Run tests, confirm pass.
6. Commit: `feat(scope): derive inspect_scope + detector presets from LSF annotations`

**Verification:**
- [ ] Test passes
- [ ] All 9 criteria mapped to ≥1 detector
- [ ] `solder_short` correctly tagged whole-side-only (rejected if scope_mode != whole_side)
- [ ] Unknown criteria raises typed `UnknownDefectCriterion` (not silent ignore)

### Phase 2.3: Frontend BomTable preview component + Wizard step 1

**Estimated time:** 15 min
**Design Deliverable:** BomTable token spec + Wizard step layout via `gaspol-design`.
**Files:**
- Create: `web/src/views/ProjectWizard.vue`, `web/src/components/BomTable.vue`, `web/src/api/bom.ts`, `web/src/stores/wizard.ts`
- Test: `web/src/__tests__/BomTable.spec.ts`

**Steps:**
1. Invoke `gaspol-design` for tabular density + drag-drop upload zone
2. Write failing test `BomTable.spec.ts::renders rows from props + shows total row count footer`. Expected: 0 rows.
3. Implement `api/bom.ts` (upload + list bom_items)
4. Implement `BomTable.vue` props: `items: BomItem[]`, renders virtual table (use `<TanStack Table>` or simple v-for ≤500 rows — test perf)
5. Implement `ProjectWizard.vue` shell with step indicator (1 of 3), drag-drop zone for `.xlsx/.csv`, on upload → call API → show BomTable
6. Run tests, confirm pass
7. Commit: `feat(wizard): step 1 BOM upload with parsed table preview`

**Verification:**
- [ ] Vitest passes
- [ ] Manual: upload `sample_bom.xlsx` (use fixture), see parsed table
- [ ] Empty state, loading state, error state all rendered
- [ ] Multi-designator rows displayed as N rows (not single comma-joined row)
- [ ] No `console.log` left in code

---

## M3 — LLM Client Foundation

### Phase 3.1: Ollama HTTP client + connection test

**Estimated time:** 10 min
**Files:**
- Create: `src/indusia_visual_editor/services/llm/__init__.py`, `services/llm/client.py`, `services/llm/schemas.py`
- Test: `tests/services/llm/test_client.py`

**Steps:**
1. Write failing test `test_ollama_client_can_reach_server` (skipif env `IVE_OLLAMA_URL` not set; uses real Ollama). Expected: `httpx.ConnectError`.
2. Run, see fail (skip if no Ollama)
3. Implement `OllamaClient` (async httpx) with `generate(model, prompt, images=None, format=None) -> str` and `chat(model, messages, format=None) -> str`
4. Wire env vars: `IVE_OLLAMA_URL` (default `http://localhost:11434`), `IVE_OLLAMA_MODEL_PLANNER` (default `gemma4:31b`), `IVE_OLLAMA_MODEL_PRELABEL`, `IVE_OLLAMA_TIMEOUT` (default 120s)
5. Add `tests/conftest.py` fixture `ollama_available()` that pings `/api/tags`
6. Run tests against running Ollama instance, confirm pass
7. Commit: `feat(llm): Ollama async HTTP client with timeout + image support`

**Verification:**
- [ ] Test passes against real Ollama (or skips cleanly when unavailable with `pytest.skip` reason)
- [ ] Client handles `httpx.ConnectError`/`TimeoutException` and raises a typed `LlmError` (don't leak httpx errors to callers)
- [ ] No API key/secret embedded in code
- [ ] Image arg accepts list of base64 PNGs (verify with simple 1×1 test image)

### Phase 3.2: Pydantic structured-output schemas

**Estimated time:** 10 min
**Files:**
- Modify: `services/llm/schemas.py`
- Test: `tests/services/llm/test_schemas.py`

**Steps:**
1. Write failing tests for: `ProposedPipeline.model_validate_json`, `PreLabeledRegion.model_validate_json`, `DefectVerdict.model_validate_json`, each with a hand-crafted valid + invalid JSON sample. Expected: `ImportError` from missing schema.
2. Run, see fail
3. Implement schemas exactly as design section §5.4 (ProposedPipelineStep, ProposedPipeline, PreLabeledRegion, DefectVerdict, ChatTurn)
4. Add field validators: bbox values 0..1, confidence 0..1, designator regex `^[A-Z]+[0-9]+$`
5. Run tests, confirm pass
6. Commit: `feat(llm): pydantic schemas for planner, prelabel, judge, advisor outputs`

**Verification:**
- [ ] All schema roundtrip tests pass
- [ ] Invalid JSON (missing field, out-of-range value) raises `ValidationError`
- [ ] `model_json_schema()` output reviewed manually for Ollama `format` param

### Phase 3.3: Planner skeleton (prompt template + dry-run)

**Estimated time:** 15 min
**Files:**
- Create: `services/llm/planner.py`, `services/llm/prompts/planner.md`
- Test: `tests/services/llm/test_planner.py`

**Steps:**
1. Write failing test `test_planner_returns_proposed_pipeline_for_minimal_input` — feeds 1 BOM item ("R1, 10kΩ, 0805") + a 256×256 dummy PNG, expects `ProposedPipeline` with ≥1 step. Skipif no Ollama. Expected: `ImportError`.
2. Run, see fail (skip ok)
3. Write `prompts/planner.md` — system prompt explaining graphflow node types, BOM context, output JSON shape. Reference `docs/specs/graphflow-config-schema.md` from Phase 0.2.
4. Implement `planner.py::propose_pipeline(bom_items: list[BomItem], golden_image_bytes: bytes) -> ProposedPipeline` — render prompt, call `client.generate(model=planner_model, prompt=rendered, images=[b64(golden)], format=ProposedPipeline.model_json_schema())`, parse with `ProposedPipeline.model_validate_json`
5. Run test against real Ollama, confirm output validates. Iterate prompt until consistent JSON.
6. Commit: `feat(llm): planner skeleton — BOM+golden → ProposedPipeline JSON`

**Verification:**
- [ ] Test passes (or skips with reason)
- [ ] Output JSON validates against `ProposedPipeline` 100% of time across 5 retries (log retries for prompt tuning)
- [ ] Prompt file is plain markdown, no hardcoded customer data
- [ ] Timing logged — planner call latency recorded for budget tracking

### Phase 3.4: Planner route + integration test

**Estimated time:** 10 min
**Files:**
- Create: `routes/llm.py`
- Modify: `main.py`
- Test: `tests/routes/test_llm.py`

**Steps:**
1. Write failing test `test_planner_endpoint_returns_proposed_pipeline_for_project_with_bom_and_golden` — uses TestClient, project pre-seeded with bom_items and golden_top asset, POST `/api/projects/{id}/llm/plan`. Expected: 404.
2. Run, see fail
3. Implement `POST /api/projects/{id}/llm/plan` — fetch bom_items + golden_top asset → call `planner.propose_pipeline` → save result to `proposed_pipelines` table → return `{status, message, data: ProposedPipeline}`
4. Add migration for `proposed_pipelines` table (Phase 1.1 didn't include it)
5. Run tests, confirm pass
6. Commit: `feat(llm): /api/projects/{id}/llm/plan endpoint with persistence`

**Verification:**
- [ ] Test passes
- [ ] `proposed_pipelines` row persisted with version incremented per project
- [ ] Endpoint returns 422 if golden_top missing or bom_items empty
- [ ] OpenAPI shows endpoint with example response

---

## Future milestones (roadmap — re-invoke `gaspol-plan` to detail)

### M4 — Planner adapter → service config.yaml + write
**Triggered AFTER labeling complete and saved** (post-decision #12). Reads `labels.ls_json` for project + side, joins to `bom_items` where `inspect_scope='inspected'` and uses derived `detector_presets`. Generate graphflow `config.yaml` + `locations.yaml` + `components/*.yaml` per-component DAG. POST to `auto-inspect-service /api/setup/...` (verify schema in Phase 0.2 spike).

### M5 — Pre-label assistant (auto-labels ALL BOM designators)
`/api/projects/{id}/llm/prelabel?side=top|bottom` — call Gemma 4 with: golden sample image + (optional) PCB drawing image + BOM list (all items, not subset). Gemma outputs bbox + class for EVERY designator it can locate. Bake predictions[] into the LSF task JSON served to canvas. User reviews + corrects in canvas. Two-image conditioning (golden + drawing) significantly improves pre-label recall because drawing gives spatial prior even when component is partially occluded in golden.

### M6 — Labeling canvas (LSF embed with unified scope+criteria UX)
Vue wrapper around LSF (Apache-2.0 React island per [`label-studio-adoption.md`](../specs/label-studio-adoption.md)). Config builder emits:
- `<RectangleLabels name="component">` with one `<Label>` per BOM designator (color-coded by `component_type`)
- `<Choices name="inspect_scope" perRegion required>` — inspect / skip
- `<Choices name="defect_criteria" perRegion multiple visibleWhen="inspect_scope=inspected">` — multi-select from defect taxonomy
- Whole-side mode: alternative LSF view with `<BrushLabels>` only (for "solder short whole bottom side" pattern)

Visual feedback: CSS overlay dims regions with `inspect_scope=skipped` (low opacity) so user sees coverage map at a glance.

On submit: backend calls `services/inspect_scope/derive.py` (Phase 2.2c) to translate annotations → `bom_items.inspect_scope` + `detector_presets` updates. Then M4 planner can run.

### M7 — Training integration
Wrap `auto-inspect-service /api/training/start`, relay SSE progress to frontend, persist `train_runs` rows + metrics.

### M8 — Gate 1 UI (training approval)
Preview dataset stats, AI-suggested epochs/augmentation, "Start Training" button gated behind explicit user click.

### M9 — Eval view
Metric charts (mAP, F1, confusion matrix), sample predictions grid, comparison vs previous run.

### M10 — Gate 2 + promote-to-production
"Promote" button → call `auto-inspect-service` to push weights to Git+LFS registry. Decide REST vs subprocess in spike at this milestone.

### M11 — Edge notification + version pin
Per-edge config: auto-pull-latest vs pinned-version. Webhook from visual-editor → edge `/api/models/refresh-cache`. Edge runs `ais model pull` on receipt.

### M12 — Chat advisor
Slide-out chat drawer; Gemma sees project metadata + result history + relevant ROI crops; suggests retraining or config tweaks.

### M13 — Auth + multi-user
JWT email/password, basic user table, project ownership, simple roles (admin / engineer / viewer).

### M14 — Polish + deploy
Production Dockerfiles, Traefik config, Postgres backup strategy, log shipping, deployment runbook.

---

## Cross-cutting non-functional requirements

- **Logging:** structured (`structlog`) with `project_id`, `train_run_id` correlation fields
- **Metrics:** OpenTelemetry-ready spans on LLM calls + service calls (defer collector wiring to M14)
- **Error handling:** All LLM/service calls wrapped — surface typed `LlmError`, `InspectServiceError`, `AssetError`. Map to HTTP responses via FastAPI exception handlers (match existing `auto-inspect-service` pattern)
- **Performance budget v1:** Planner call ≤30s, pre-label ≤60s, BOM parse ≤2s for 500 rows, labeling canvas 60fps for ≤300 regions
- **Anti-AI-slop in UI:** Bahasa Indonesia copy reviewed (no "leverage", "synergi", "revolusi"); concrete verbs only; technical terms English

---

## Appendix A — Merged from `2026-03-14-visual-editor-design.md`

> Merged 2026-05-22. Old file deleted; this is now the single source of truth.
> Sections A.1–A.8 preserve technical content from the earlier brainstorm that the new MVP plan above (M0–M14) does not yet detail. Tag with milestone where each item lands.

### A.1 — On-Premise / Cloud Topology (refines decision #5 + the architecture diagram in §3)

**Decision (carried forward):** Cloud UI on VPS hosting + on-premise Agent at customer site. PCB images never leave customer site (privacy). Visual Editor cloud accesses local images via Agent WebSocket proxy stream — no cloud storage of PCB photos.

**Three-service on-premise topology (NOT one monolith):**

```
indusia-agent (Nuitka ELF binary) — ORCHESTRATOR (NEW code)
├─ WebSocket client → cloud Visual Editor
├─ License validator (cached JWT, 7-day offline grace)
├─ Label Studio annotation UI (localhost:8080) — LSF embed per adoption doc
│   └─ BOM panel + confidence overlay + drawing overlay
├─ Ollama client → Gemma 4 / Qwen2.5-VL for auto-label (decision #6: dedicated GPU box; this client lives in agent for v1 single-box, future split)
├─ SAM 2.1 executor (local GPU, bbox refinement)
├─ BOM Parser (openpyxl + LLM for complex formats)
├─ Training executor (anomalib + YOLO11)
├─ Config generator (BOM → YAML pipeline configs)
├─ Image proxy (serve local images to cloud UI via WS)
└─ Health monitor (GPU/CPU/RAM → heartbeat)

auto-inspect-service (:8001) — EXISTING, untouched
└─ graphflow engine + YOLO11 + anomalib + fiducial + OpenVINO

auto-inspect-edge (:8002) — EXISTING, untouched
└─ Hikrobot camera + PLC + frame capture + SSE

Ollama (:11434) — customer installs separately OR runs on dedicated GPU box per decision #6
└─ gemma4:31b for auto-labelling / planner / judge / advisor
```

**Hardware reference spec (per customer site):** i7-13700K · RTX 5060 Ti 8GB (minimum) — note: per decision #6 production deployment uses dedicated GPU box for `gemma4:31b` (24GB+) separate from training/inference GPU. Single-box deployment of all 3 services is dev/PoC mode only. · 32GB DDR5 · 1TB NVMe + 2TB SATA · Ubuntu Server 22.04 LTS.

**Local data layout (never leaves customer site):**
```
/data/datasets/{board}/golden-samples/   ← PCB images
/data/datasets/{board}/pnp/              ← Pick & Place
/data/datasets/{board}/drawings/         ← PCB Drawings
/data/datasets/{board}/bom/              ← BOM files
/data/datasets/{board}/overrides/        ← False call images
/data/models/{board}/{version}/          ← Trained weights
/data/exports/model_package_{board}.zip  ← Export packages
/data/configs/{board}/config.yaml        ← Pipeline configs
```

**Cloud-side (VPS + Docker Compose):**
```
LABEL STUDIO FORK / indusia-visual-editor frontend :8080
├─ Dashboard (project overview, agent status, FCR)
├─ Project management
├─ Training dashboard (view progress from agent over WS)
├─ Eval dashboard (metrics charts, model comparison)
├─ Model registry (version history, export packages)
├─ False call monitor (FCR trends, override images)
├─ License enforcement (model count, expiry)
├─ Multi-tenant (organization-based isolation)
└─ WebSocket hub (agent communication)

PostgreSQL (multi-tenant) │ Redis (WS + cache) │ License Server (API) │ MinIO (model packages only — NOT PCB images)
```

**Port map (on-premise):**

| Service | Port | Role |
|---|---|---|
| auto-inspect-service | 8001 | Inference engine (graphflow + models) |
| auto-inspect-edge | 8002 | Hardware integration (camera, PLC) |
| Ollama | 11434 | LLM inference (gemma4:31b) |
| indusia-agent | (local socket) | Orchestrator |
| Visual Editor UI (cloud) | 443 | Multi-tenant SPA, serves to factory browser |

**This refines plan-level architecture decision #9 ("Path A — Lean monolith"):** Path A applies to **cloud-side `indusia-visual-editor`**. Customer-site deployment is the agent binary + existing services (unchanged). The Cloud↔Agent boundary is the WebSocket + signed JWT.

### A.2 — Training Strategy (Hybrid YOLO11 + DINOv2/CFA)

**Lifecycle progression** (auto-suggested by Visual Editor based on accumulated data):

| Model | When | Training data | Time | Acc | Export |
|---|---|---|---|---|---|
| **YOLO11 Classification** | Enough good + defect images | good/ + defective/ + missing/ | 5–10 min | 95%+ | PyTorch .pt |
| **DINOv2 Anomaly** | New board, no defect samples | good/ only | 1–2 min | 85–92% | OpenVINO IR |
| **CFA (ResNet50)** | Pin/lead inspection | good/ only | 2–3 min | 85–90% | OpenVINO IR |
| **PatchCore** | Alt anomaly | good/ only | 1–2 min | 85–92% | OpenVINO IR |

```
Week 1–2: New board → DINOv2 Anomaly (golden only)        Acc 85–92%
Week 3–8: Accumulate good/defect/missing via overrides
Week 8+:  Switch component group → YOLO11 Classification   Acc 95%+
          Visual Editor UI surfaces: "GRP_0603 has 240/18/12 samples — switch from DINOv2 to YOLO11? [Switch & Retrain]"
```

**Framework versions:**

| Framework | Version | Purpose |
|---|---|---|
| anomalib | 0.7.4 | DINOv2, CFA, PatchCore |
| Ultralytics YOLO | latest | YOLO11 cls/OBB/detect |
| graphflow | 0.1.3 | Pipeline node-graph |
| OpenVINO | latest | CPU export for HMI |
| PyTorch Lightning | latest | Training orchestration |

**DINOv2 production params:** `dinov2_vit_small_14`, coreset 0.1, num_neighbors 1, sigma 4.0, normalize min_max, imgsz 252×252, 1 epoch.

**YOLO11 production params:** `yolo11m-cls.pt`, imgsz 224, 100 epochs, patience 20, batch 16, optimizer auto, augmentation Albumentations multiplier ×20 (see §A.8).

**Auto-generated graphflow per group** (example `/data/configs/{board}/components/group_0603.yaml`):

```yaml
nodes:
  - { name: input,      type: input }
  - { name: yolo_crop,  type: yolo_crop,
      params: { classes: ["0603"], expand_ratio: 1.5, min_size: [40, 40] } }
  - { name: estimator,  type: yolo_estimator,
      params: { weight_path: "/data/models/{board}/v3/group_0603/weights/best.pt" } }
  - { name: transform,  type: transform_result, params: { classes: ["0603"] } }
  - { name: output,     type: merge_result }
edges:
  - [input, yolo_crop]
  - [yolo_crop, estimator]
  - [estimator, transform]
  - [transform, output]
```

**Lands in:** M4 (planner adapter — emits this YAML), M7 (training).

### A.3 — False Call Feedback Loop

**Flow:**
```
HMI (operator) → "Override: PASS" + reason tag
   ↓
Agent: save image to /data/overrides/ + update FCR counter
   ↓
WebSocket notify cloud (designator + score + reason + FCR — NOT the image)
   ↓
Cloud DB: override_logs, FCR dashboard, threshold check
   ↓
Engineer reviews override (image streamed on-demand from agent WS proxy — never cloud-stored)
   ↓
Decision: adjust threshold | add to training set | retrain group
```

**FCR thresholds:**

| FCR | Action |
|---|---|
| <2% | Healthy |
| 2–5% | Notify engineer (dashboard warning) |
| >5% | Critical — auto-suggest retrain |
| >10% | Emergency — pause auto-pass, all components → REVIEW mode |

**Operator override UI** (HMI) requires reason selection — solder variation / lighting artifact / color variance / contamination / other. Captured for later analysis.

**Lands in:** v1.5 (after main training loop stable). Add `override_logs` table in DB schema when implemented.

### A.4 — Licensing Architecture

**Model:** per-customer license, model-count limit (default 30), dual-product enforcement (Visual Editor + HMI share counter).

**Schema:**
```sql
license_keys
  id UUID PK
  customer_id UUID FK → organizations
  product TEXT CHECK (product IN ('editor','hmi','both'))
  max_models INT DEFAULT 30
  models_used INT DEFAULT 0
  issued_at TIMESTAMPTZ
  expires_at TIMESTAMPTZ
  license_key TEXT UNIQUE        -- signed JWT
  status TEXT CHECK (status IN ('active','expired','suspended'))
```

**Enforcement points:**

| Layer | Method | Bypass difficulty |
|---|---|---|
| Cloud DB (primary) | Postgres check before model create | Impossible — customer no DB access |
| Agent token (secondary) | Cached signed JWT, refresh 24h | Very hard — JWT signed by cloud private key |
| HMI license (tertiary) | API or embedded file | Hard — HMI compiled/obfuscated |

**State machine:**

| State | Read | Create/Train | Export/Deploy |
|---|---|---|---|
| Active | ✓ | ✓ | ✓ |
| >80% used | ✓ + banner | ✓ + "X remaining" | ✓ |
| At limit | ✓ | BLOCKED + upgrade CTA | BLOCKED |
| Expired 0–30d | ✓ (grace) | BLOCKED | BLOCKED |
| Expired >30d | BLOCKED | BLOCKED | BLOCKED |

**Sidebar UI:** progress bar `12/30 models` + expiry date.

**Lands in:** M13 (auth/multi-user) onward. Cloud-side license server is a separate service or table inside `indusia-visual-editor`.

### A.5 — Agent Code Protection (Nuitka)

**Stack:**

| Layer | Technique | Protection |
|---|---|---|
| 1. Pre-obfuscate | PyArmor BCC (Python → C → ELF) | Medium |
| 2. Compile | Nuitka `--onefile` (Python → C → native binary) | Very High |
| 3. Anti-debug | Nuitka `--protect` | High |
| 4. Strip + pack | `strip` + UPX | Medium |
| 5. License | Cloud JWT + local cache | Very High |

**Why Linux:** fewer reverse-engineering tools vs Windows PE; SSH-only access; hardware engineers usually unfamiliar with Linux internals. Nuitka does NOT cross-compile — build ON Linux (CI/CD or build server).

**Customer can see:** agent binary (ELF, compiled), `agent.yaml` (server URL, auth token), SAM 2.1 weights (open source), local data dirs (their own data).

**Customer cannot see:** source, communication protocol details, training pipeline logic, BOM matching algorithms, license internals, cloud API auth.

**Key insight:** even if reverse-engineered, attacker only gets a WS client (useless without cloud auth) + wrappers around open-source tools. All proprietary business logic = cloud-side.

**Lands in:** M14 (production deploy hardening). Build pipeline: CI/CD with Linux runner produces signed binary per release.

### A.6 — Design System Tokens

**Philosophy:** Industrial Precision Dark — OLED dark + flat + PCB-inspired accents. Factory/lab environment requires high contrast, zero ambiguity, instant status recognition.

**Anti-patterns:** light mode default · emojis as icons · rounded playful shapes · purple/pink accents · glassmorphism blur · animations >300ms.

**Color tokens (dark mode primary):**

```css
/* Surfaces */
--bg-deep: #020617;       /* app shell */
--bg-base: #0B1120;       /* PCB substrate */
--bg-elevated: #111827;   /* cards/panels */
--bg-hover: #1A2236;
--bg-active: #1E293B;

/* PCB green brand */
--primary: #22C55E;
--primary-hover: #16A34A;
--primary-muted: rgba(34,197,94,0.15);
--primary-glow: rgba(34,197,94,0.25);

/* Status palette */
--secondary: #3B82F6;     /* signal blue */
--warning:   #F59E0B;     /* amber */
--danger:    #EF4444;     /* red */
--success:   #10B981;     /* emerald */
/* + -muted variants at 0.15 alpha */

/* Text hierarchy (WCAG AAA on dark bg) */
--text-primary: #F1F5F9;     /* 15.4:1 */
--text-secondary: #94A3B8;   /* 6.8:1 */
--text-tertiary: #64748B;    /* 4.6:1 */
--text-disabled: #475569;
--text-on-primary: #0F172A;

/* Borders */
--border: #1E293B;
--border-hover: #334155;
--border-active: #22C55E;
--border-focus: #3B82F6;   /* 3px solid */
```

Light-mode pair shipped for documentation/office use (deeper saturation: primary `#16A34A`, danger `#DC2626`, surfaces `#F8FAFC`/`#FFFFFF`).

**Confidence overlay (bbox colors):**

| Level | Border | Fill | Trigger |
|---|---|---|---|
| High | `#22C55E` 2px solid | 12% | conf > 0.85 |
| Medium | `#F59E0B` 2px solid | 12% | 0.60–0.85 |
| Low | `#EF4444` 2px solid + pulse | 15% | < 0.60 |
| Missing | `#6B7280` 2px dashed | none | not detected |
| VLM override | `#8B5CF6` 2px solid | 10% | judge applied |

**Typography:** Fira Code (data/metrics, ligatures + tabular figures) · IBM Plex Sans (UI text, industrial heritage) · JetBrains Mono (logs/terminal). Load via Google Fonts.

| Role | Font | Wgt | Size | LH |
|---|---|---|---|---|
| Page Title | IBM Plex Sans | 700 | 28px | 1.2 |
| Section | IBM Plex Sans | 600 | 20px | 1.3 |
| Body | IBM Plex Sans | 400 | 14px | 1.5 |
| Label | IBM Plex Sans | 500 | 12px | 1.4 (uppercase tracking +0.05em) |
| Data Value | Fira Code | 600 | 24px | 1.2 |
| Data Small | Fira Code | 400 | 14px | 1.4 |
| Log | JetBrains Mono | 400 | 13px | 1.5 |
| Badge | IBM Plex Sans | 600 | 11px | 1 |

**Spacing (strict 8dp grid):** 4/8/12/16/20/24/32/40/48px (tokens `--space-1..12`).

**Radius (sharp, industrial):** 0 (tables/terminal) / 4 (buttons/inputs/badges) / 6 (cards) / 8 (modals) / 9999 (dots/avatars).

**Elevation (dark mode — subtle inner border instead of heavy shadow):**
```css
--shadow-1: 0 1px 2px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.04);
--shadow-2: 0 4px 12px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.06);
--shadow-3: 0 8px 24px rgba(0,0,0,.6), 0 0 0 1px rgba(255,255,255,.08);
--shadow-glow: 0 0 20px rgba(34,197,94,.15);   /* primary CTA */
```

**Icons:** Lucide React, 1.5px stroke, sizes 16/20/24, color inherits text token. **No emoji icons ever.** Active nav uses filled variant.

**Motion:**

| Type | ms | Easing | Usage |
|---|---|---|---|
| Micro | 150 | ease-out | hover/badge |
| Standard | 200 | cubic-bezier(0.4,0,0.2,1) | panel/tab |
| Complex | 300 | cubic-bezier(0.16,1,0.3,1) | modal enter, page |
| Exit | 150 | ease-in | modal close |
| Data | 400 | ease-out | charts, progress |

Respect `prefers-reduced-motion`. No animation >500ms (feels laggy). Use skeleton shimmer for loading >300ms. Real-time data updates: instant paint, no animation. Stagger lists 30ms max 10 items.

**Component patterns** (status dot, KPI card, data table, sidebar nav, stepper, charts) — full ASCII mockups in source extracts; reproduce in `web/src/components/` and document in Storybook during M1+.

**Accessibility:** WCAG AAA on dark · 3px focus ring · color never sole indicator · keyboard full-tab + A/R/N/P annotation shortcuts · all charts have data-table alt · status dots always paired with text label.

**Responsive:** mobile <768 (hamburger) · tablet 768–1024 (collapsed sidebar 64px) · desktop 1024–1440 (sidebar 260px) · wide >1440 (max content 1440 centered).

**Lands in:** Phase 1.4 onward (every UI phase invokes `gaspol-design` with these tokens as input).

### A.7 — Model Library Roadmap

**Phase 1 (MVP):** per-customer training from scratch — what M0–M14 ships.

**Phase 2 (+6 mo):** cross-board transfer learning within same customer — warm-start new boards from existing trained models of similar package types. Cuts training time 5min → 1min, higher starting accuracy.

**Phase 3 (+12 mo):** **Indusia Model Library** — cloud-side anonymized base models per package type, accumulated from customer data (model features only, NO images uploaded). Fine-tune per customer with their golden samples.

| Package | Base Acc | Fine-tune | Final Acc |
|---|---|---|---|
| 0603 R | 88% | 30s | 95%+ |
| 0402 C | 85% | 30s | 93%+ |
| QFN-48 | 82% | 1min | 90%+ |
| SOIC-8 | 84% | 1min | 92%+ |
| SOT-23 | 86% | 30s | 94%+ |

This is the **competitive moat** — built from real factory data, can't be replicated by anyone without similar customer base.

### A.8 — Lighting Robustness & Augmentation

**Root cause:** production AI fragile because trained on images from ONE lighting condition. Vision models reason on pixel values (not semantic like LLMs) — brightness shift +10% changes ALL pixel values → model fails.

**Solution = augmentation + normalization, not synthetic data.**

**Albumentations pipeline (CPU only, zero GPU cost):**

```python
import albumentations as A
transform = A.Compose([
    A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.5),
    A.GaussNoise(var_limit=(10, 50), p=0.3),
    A.HueSaturationValue(hue_shift_limit=10, sat_shift_limit=20, val_shift_limit=20, p=0.3),
    A.CLAHE(clip_limit=4.0, p=0.3),
    A.RandomGamma(gamma_limit=(80, 120), p=0.3),
    A.GaussianBlur(blur_limit=3, p=0.2),
    A.ColorJitter(brightness=0.1, contrast=0.1, saturation=0.1, hue=0.05, p=0.3),
])
# 50 originals × 20 variants = 1,000 training images
# Augmentation cost: +30s, accuracy: ~10–30% fewer false calls
```

**Pre-inference normalization** (every frame before inference):
1. CLAHE — local contrast normalize
2. White-balance correct — remove color cast
3. Brightness normalize to reference
4. Histogram match to golden sample

**Reference image calibration** (Visual Editor setup step):
- Capture golden sample under STANDARD lighting → record histogram profile
- Every inference: compare current frame vs reference → auto-adjust → feed normalized image
- If histogram deviation > threshold → alert "Lighting drift, recalibrate camera"

**⛔ Do NOT use AI image generation for PCB training data.** Pixel accuracy required (good vs cold solder = few pixels). AI-generated images hallucinate details, fabricate solder reflections, get markings wrong → trains model on FALSE patterns. Confirmed in production testing.

**✅ Valid synthetic augmentation** (pure image processing, not generative AI):
- Brightness/contrast/gamma (Albumentations)
- Copy-paste augmentation — crop real component, paste to other positions
- Cutout/Erasing — simulate missing component
- Color transfer from different real captures
- Geometric — rotate/flip/slight perspective warp

**Training Manager UI augmentation panel** (per training job): sliders for brightness/contrast/gamma/noise/jitter/blur ranges + multiplier (default 20×) + "Preview augmented samples" button + "Reset to default".

**Lands in:** M7 (training integration) — Visual Editor exposes augmentation config in training trigger payload, `auto-inspect-service` applies Albumentations during training.

---

## Execution handoff

**Option 1: Execute in this session**
> Ready to start Phase 0.1? I'll use `gaspol-execute` to implement with per-phase checkpoints + TDD gate.

**Option 2: Parallel execution**
> M0 phases 0.1, 0.2, 0.3 are independent — can run via `gaspol-parallel` (mode: plan-phases). Phase 0.4 depends on 0.1.

**Option 3: Separate session**
> Plan is saved at `docs/plans/2026-05-22-visual-editor-mvp.md`. Start a fresh session with `gaspol-execute` referencing this file.
