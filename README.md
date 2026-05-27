# Indusia Visual Editor

> **From PCB photo to production inspection in hours, not days.** Zero YAML, zero CLI, zero computer-vision expertise required from the factory user.

<p align="left">
  <a href="docs/plans/2026-05-22-visual-editor-mvp.md"><img src="https://img.shields.io/badge/backend-M0--M14_shipped-047857?style=flat-square" alt="backend status" /></a>
  <a href="docs/plans/2026-05-27-vue-fe-migration.md"><img src="https://img.shields.io/badge/frontend-F0--F6_shipped-047857?style=flat-square" alt="frontend status" /></a>
  <img src="https://img.shields.io/badge/tests-395_backend_%2B_36_unit_%2B_8_e2e_passing-047857?style=flat-square" alt="tests passing" />
  <img src="https://img.shields.io/badge/license-proprietary-475569?style=flat-square" alt="license" />
</p>

![Dashboard](docs/design/screens/02-dashboard.png)

---

## The problem

PCB factories run two lines: **SMT** (surface mount, fully automated, AOI machines catch defects) and **MI** (manual insertion — through-hole components like electrolytic caps, connectors, DIP ICs, headers — soldered through a wave bath). Today **no inspection automation exists for MI**. Tired operators visually check every board for lifted pins, polarity flips, wrong values, and missing components. The miss rate is whatever-it-is.

The standard fix — hire a computer vision team, write graphflow YAML configs, train per-PCB models — takes weeks per board and assumes the factory has data scientists on payroll. Most don't.

## The fix

A web app where a manufacturing engineer who has never written Python takes a brand-new PCB from photo to a model running on the production line in **one afternoon**:

```
Upload BOM → Upload golden photo (top + bottom) → Label defects
                                                        ↓
                  Promote ←  Eval  ← Train  ←  AI plans the pipeline
```

Two manual gates (**Gate 1** before training, **Gate 2** before deploy) keep the human in the loop where it counts. Everything else is automatic — Gemma 4 plans the pipeline, pre-labels every component, suggests training hyperparameters, and answers your follow-up questions from a chat drawer.

## What it looks like

The full UI lives in [Figma](https://www.figma.com/proto/bbNj0YkQGJr2GpsvAaSS3R?node-id=6-2&starting-point-node-id=6%3A2) (39 screens, dual-locale EN+ID, operator + engineer modes). Highlights:

### 1. Sign in
Single-tenant deployment, on-prem ready. Bahasa Indonesia switch lives in the top bar.

![Sign in](docs/design/screens/01-login.png)

### 2. Dashboard
Each PCB project is a card with status (drafting / training / deployed). The right rail has a 4-step quick-start and a Gemma 4 advisor on standby.

![Dashboard](docs/design/screens/02-dashboard.png)

### 3. Labeling canvas
Label Studio Frontend embedded as a React island inside Vue 3. Designators flow from the BOM into RectangleLabels; Gemma 4 has already drawn the green prediction boxes. The operator corrects mistakes, picks defect criteria per region, then saves.

![Labeling canvas](docs/design/screens/03-labeling.png)

### 4. Gate 1 — training preparation
Dataset readiness (sufficient / moderate / at-risk buckets per designator), training-mode picker, three considerations the operator must read, and an engineer-mode reveal with the full hyperparameter grid (epochs, batch size, LR, augmentation intensity).

![Gate 1 — training preparation](docs/design/screens/04-gate1.png)

### 5. Live training
Epoch progress strip, per-component state table (Done / Training / Queued), live mAP / F1 / Precision / Recall. Engineer mode reveals optimizer, GPU memory, and a tailing log terminal.

![Training](docs/design/screens/05-training.png)

### 6. Evaluation passed
Threshold-coded metrics (mAP ≥ 0.80, F1 macro ≥ 0.80, per-component F1 ≥ 0.70). Failing components surface as red tiles the operator can click to jump straight into correction mode for the offending samples. Once everything is green, **Promote** unlocks.

![Eval passed](docs/design/screens/06-eval-passed.png)

### 7. Gate 2 — confirm deployment
Final HITL gate. Operator sees model snapshot + registered edges (online/offline pills). Engineer reveal shows SHA256, registry tag, rollback target, and the literal `ais model push` command. Promote fires a modal interception then a success toast.

![Gate 2 — confirm deployment](docs/design/screens/07-gate2.png)

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser — Vue 3.5 + TS strict + Pinia + Vite 7                   │
│ AppShell (Sidebar · TopBar · ChatDrawer · ToastStack)            │
│ 39 screens · EN+ID · operator+engineer modes · LSF canvas        │
└─────────────────────────────┬────────────────────────────────────┘
                              │ HTTPS · REST + SSE
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ indusia-visual-editor — FastAPI service (this repo)              │
│   routes/   auth · project · asset · bom · label · llm ·         │
│             training · eval · deploy · edges · chat · adapt      │
│   services/ asset · project · label · llm · inspect_service ·    │
│             deploy · edge · auth · inspect_scope                 │
│   db/       Postgres 16 (12 tables, migrations 0001-0011)        │
│   utils/    structlog (JSON) · OpenTelemetry (auto + manual)     │
│   storage/  filesystem with SHA256 dedup, 50MB cap               │
└──┬──────────────────┬──────────────────────────┬─────────────────┘
   │ HTTP             │ HTTP                     │ HTTP / webhook
   ▼                  ▼                          ▼
┌─────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐
│ Ollama      │  │ auto-inspect-       │  │ auto-inspect-edge       │
│ gemma4:31b  │  │ service (:8001)     │  │ (:8000, on-prem)        │
│ 256K ctx    │  │ — graphflow engine, │  │ — PLC, Hikrobot camera, │
│ dedicated   │  │ training, model     │  │ pulls weights via       │
│ GPU box     │  │ registry (Git+LFS)  │  │ `ais model pull`        │
└─────────────┘  └─────────────────────┘  └─────────────────────────┘
```

**Data privacy promise**: PCB images never leave the factory. The on-prem agent handles labeling + training + inference; only model weights and metadata reach Indusia's cloud control plane.

## Why it works

| Decision | Rationale |
|---|---|
| Embed Label Studio Frontend as a React island in Vue 3 (Apache-2.0) | Canvas, bbox, polygon, brush, keypoint, zoom, history, hotkeys, LS-JSON output — all free. Saves ~3 weeks of custom Konva work. |
| Gemma 4 plays four roles: planner, pre-label, runtime defect judge, advisor | One brain across the platform. 256K context, structured output validated by pydantic. Defect-judge stays deferred to v1.5. |
| Reuse `auto-inspect-service` for training + inference unchanged | Battle-tested YOLO + Anomalib + OpenVINO + fiducial + OCR stack. We orchestrate, we don't reinvent. |
| Two mandatory HITL gates (Gate 1 before training, Gate 2 before deploy) | Production safety. Never auto-approve, even when metrics are green. |
| User-controlled per-region inspect scope in canvas (not BOM filter) | Trust user judgment. Smart MI/SMT heuristic defaults but full override. |
| Vendored LSF binary checked into `web/public/lsf/` (~7.5 MB) | Reproducible deploys. No npm-install dependency on Label Studio's build infrastructure. |
| Direct push to `main`, no feature branches | Solo-developer project per [CLAUDE.md §13.5](CLAUDE.md). Branching is opt-in only when explicitly requested. |

## Status

| Layer | Status | Notes |
|---|---|---|
| Backend | **M0–M14 shipped** | 395 tests passing · Auth (M13) · Production hardening (M14) · structlog + OpenTelemetry · Traefik + Postgres backup |
| Frontend | **F0–F6 shipped** | 36 unit/component + 8 Playwright e2e passing · Full 39-screen Figma parity · MSW dev-mode mocks |
| Runbook | Done | [`docs/runbook/{deploy,disaster-recovery,onboarding}.md`](docs/runbook/) |
| v1.5 | Deferred | LSF ML backend protocol · runtime defect judge · multi-tenant SaaS · M15 dual-mode persistence |

### Backend milestones

| | What landed |
|---|---|
| **M0** Bootstrap | LSF build spike, FastAPI scaffold + `/health`, graphflow config spike, Vue + Vite + Pinia + Tailwind, Docker Compose dev env |
| **M1** Project + Asset CRUD | Alembic baseline, `/api/projects` CRUD, asset upload with SHA256 dedup + 50MB cap, Dashboard view |
| **M2** BOM parser + classifier | xlsx/csv parse with multi-designator expansion, MI/SMT heuristic, `defect_detector_mapping.yaml` (9 criteria) |
| **M3** LLM client foundation | Ollama async httpx client with typed `LlmError` family + structured output, planner skeleton, `proposed_pipelines` table |
| **M4** Planner adapter → graphflow | `detector_to_nodes.yaml` (13 presets → 51 nodes), per-component subgraph builder, atomic writer with rollback, `adapt_runs` table |
| **M5** Pre-label assistant | Gemma 4 prelabel orchestrator with golden+drawing dual-image prior, `pre_labels` table (latest-wins) |
| **M6** Labeling canvas | LSF vendored at `web/public/lsf/` with sha256 manifest, `labels` table (versioned per side), `derive_inspect_scope` writes `detector_presets` onto bom_items |
| **M7** Training + SSE | `TrainingClient` with typed errors, `train_runs` table, `/api/training/start`, `/api/training/{run_id}/stream` SSE relay |
| **M8** Gate 1 | `/dataset/stats` + `suggest_hyperparams` (Gemma 4, pydantic-bounded), composer endpoint |
| **M9** Eval | `get_predictions` + `/eval` (metrics + predictions + prev-run delta) |
| **M10** Gate 2 + promote | `services/deploy/registry.push_model` async wrapper, `deployments` table, audit-row-before-502, three env vars |
| **M11** Edge notification + pin | `edges` table, exponential-backoff fan-out, per-edge `NotifyOutcome`, manual rollback via PUT `/pin` |
| **M12** Chat advisor | `chat_sessions` table, context builder (system + project + last 3 train runs + 20 turns, 600 KB budget), Bahasa Indonesia advisor prompt, SSE stream |
| **M13** Auth + roles | JWT bearer + refresh cookie, organization isolation, RBAC (admin / engineer / viewer), seed `default` org |
| **M14** Production hardening | Multi-stage Dockerfiles, Traefik v3 (ACME + secure headers), daily pg_dump + S3, structlog JSON logs + request_id middleware, OpenTelemetry auto + manual spans, full runbook |

### Frontend phases

| | What landed |
|---|---|
| **F0** Foundation | Clean `web/` (preserved `public/lsf/` + `.gitattributes`), Vite 7 + Vue 3.5 + TS strict + Pinia 2 + Tailwind 3 + Reka UI + vue-i18n 10 + MSW 2 + Vitest 2 + Playwright 1.49 |
| **F1** Shell + primitives | `AppShell`, `AppSidebar` (workspace + settings + AI advisor flush bottom), `AppTopBar` (breadcrumb + EN/ID switcher + engineer toggle + user logout), `AppButton` |
| **F2** Auth + Dashboard | LoginView + SignupView wired to backend M13 `/api/auth/*` with envelope errors, refresh-cookie + bearer interceptor, `useAuthStore` with `loadCurrentUser` rehydrate; Dashboard 8:2 layout with 4 stat cards + projects table + quick-start rail |
| **F3** Wizard | 5-step stepper (project basics → BOM → golden samples → drawing → review) wired end-to-end; `POST /api/projects` then `POST /assets?kind=` per step; BOM preview table (designator/value/package/qty/MI badge); URL rewrites `/projects/new` → real UUID after step 1 |
| **F4** Labeling | `LSFEmbed.vue` dynamic-loads `/lsf/main.{js,css}`, instantiates `window.LabelStudio` with `reactVersion:'v18'`, wires onSubmit/onUpdate/onEntityCreate to Vue emits; `RegionDetailPanel` shows X/Y/W/H/R° + designator + 8 defect-criteria checkboxes + 4 action icons; correction mode banner driven by `?correction=1&samples=...` |
| **F5** Training + Eval | `useTrainingStore` with full SSE consumer (epoch/succeeded/failed events update live metrics + per-component queue + 50-line log buffer); Gate 1 dual-mode (op default + engineer reveal); Training live view; SetupEvalView with test-set picker + readiness gates; EvalView state machine with threshold-coded metrics + failing-component tiles + verdict-driven actions (correct / retrain / promote) |
| **F6** Gate 2 + settings + overlays | Gate 2 with HITL banner + model snapshot + edges card + engineer-reveal tech details + confirm-checkbox + modal interception + promote toast; 5 settings views (Models / Edges / Datasets / Team / Preferences); `ChatDrawer` overlay (M12 SSE via fetch+ReadableStream because EventSource can't POST a body); `ToastStack` overlay with 3 variants and auto-dismiss TTL |

## Tech stack

| Layer | Choice | Version |
|---|---|---|
| Backend | Python, FastAPI, pydantic-settings, SQLAlchemy 2 async, Alembic, httpx, sse-starlette | 3.10+ / 0.121+ |
| Database | PostgreSQL | 16 |
| LLM | Ollama `gemma4:31b` on dedicated GPU | 20 GB / 256K ctx |
| Frontend | Vue, Vite, TypeScript, Pinia, vue-router, Tailwind, Reka UI, vue-i18n, axios | 3.5 / 7 / 5.7 |
| Labeling canvas | Label Studio Frontend (Apache-2.0) vendored | ~7.5 MB |
| Auth | JWT bearer + HttpOnly refresh cookie | M13 |
| Containers | Docker Compose (dev + prod) | M14 |
| Reverse proxy | Traefik v3 (auto HTTPS via Let's Encrypt) | M14 |
| Observability | structlog (JSON) + OpenTelemetry (FastAPI + httpx + manual) | M14 |
| Testing — backend | pytest + pytest-asyncio + httpx ASGITransport | 395 passing |
| Testing — frontend | Vitest + @vue/test-utils + happy-dom + Playwright | 36 unit + 8 e2e |
| Code style | black + isort + flake8 · ESLint flat + Prettier + eslint-plugin-vue | — |

## Quick start (development)

**Prerequisites**: Node 20+, Python 3.10+, Poetry 2, Docker Desktop, an Ollama instance running `gemma4:31b`.

```powershell
# 1. Database (host port 5433 → container 5432)
docker compose -f docker-compose.dev.yml up -d postgres
$env:IVE_DATABASE_URL = "postgresql+asyncpg://ive:ive@localhost:5433/ive"
poetry run alembic upgrade head

# 2. Backend on :8002
poetry install
poetry run uvicorn indusia_visual_editor.main:app --reload --host 0.0.0.0 --port 8002
# → http://localhost:8002/health

# 3. Frontend on :5173 (MSW serves dev-mode mocks until backend is up)
cd web
pnpm install
pnpm dev
# → http://localhost:5173

# Run all tests
poetry run pytest -v                           # backend (395 pass)
cd web && pnpm test:unit && pnpm test:e2e      # frontend (36 unit + 8 e2e)
```

The LSF bundle is built once from upstream `D:\Projects\label-studio` and vendored under `web/public/lsf/` — see [`docs/specs/lsf-build.md`](docs/specs/lsf-build.md).

## Quick start (factory user, post-deploy)

1. Open the platform URL in Chrome / Edge.
2. Sign in with the credentials your IT team provided.
3. Click **+ New project** → name it after the PCB model code from your customer (e.g. `NV80-017542-0501`).
4. Upload `BOM.xlsx` → review the parsed component table.
5. Upload `golden_top.jpg` + `golden_bottom.jpg`. Drop in the PCB drawing.
6. Open the labeling canvas — Gemma 4 pre-placed bounding boxes. Correct the wrong ones, pick defect criteria per region (missing / polarity / lifted pin / wrong value …).
7. Click **Approve & start training** at Gate 1.
8. Wait ~10–30 min while training streams epochs into the live view.
9. Review the eval results. Click any red component tile to enter correction mode for just those samples, then retrain.
10. Once all thresholds are green, click **Promote** at Gate 2.
11. The model is live on every online edge. Use the chat drawer (bottom-right `?` button) if anything surprises you.

## Repository layout

```
indusia-visual-editor/
├── src/indusia_visual_editor/   FastAPI service (routes · services · db · schemas · utils)
├── web/                         Vue 3 SPA (api · stores · components · views · i18n · mocks · tests)
├── tests/                       backend pytest suite + fixtures
├── docs/
│   ├── design/screens/          Figma hero screens (this README pulls from here)
│   ├── plans/                   gaspol-plan output (M0–M14 backend, F0–F6 frontend)
│   ├── specs/                   ML dual-mode workflow, LSF adoption, graphflow schema, ais-model-push
│   ├── runbook/                 deploy · disaster recovery · operator onboarding
│   ├── roadmap/                 deferred-to-v1.5
│   └── archive/                 superseded designs (kept for traceability)
├── alembic/                     DB migrations 0001 → 0011
├── data/                        committed YAML data (taxonomy, detector mapping)
├── infra/                       Traefik + Postgres backup scripts (M14)
├── docker-compose.dev.yml       dev environment (postgres on :5433)
├── docker-compose.prod.yml      prod environment (traefik + api + web + postgres + backup)
├── pyproject.toml               Poetry project
├── CLAUDE.md                    project memory — read FIRST every session
└── README.md                    this file
```

## Documentation map

| Doc | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Project memory — authoritative current-state inventory, conventions, anti-hallucination rules. **Read first.** |
| [docs/plans/2026-05-22-visual-editor-mvp.md](docs/plans/2026-05-22-visual-editor-mvp.md) | Backend M0–M4 plan |
| [docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md](docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md) | Backend M5–M14 plan |
| [docs/plans/2026-05-27-vue-fe-migration.md](docs/plans/2026-05-27-vue-fe-migration.md) | Frontend F0–F6 design + plan |
| [docs/specs/ml-workflow-dual-mode.md](docs/specs/ml-workflow-dual-mode.md) | ML workflow naming + operator/engineer dual-mode UI spec |
| [docs/specs/label-studio-adoption.md](docs/specs/label-studio-adoption.md) | LSF embedding strategy + boundary |
| [docs/specs/lsf-build.md](docs/specs/lsf-build.md) | Verified LSF build procedure |
| [docs/specs/graphflow-config-schema.md](docs/specs/graphflow-config-schema.md) | auto-inspect-service config + locations schema |
| [docs/runbook/deploy.md](docs/runbook/deploy.md) | First-time bootstrap + routine re-deploy + rollback |
| [docs/runbook/disaster-recovery.md](docs/runbook/disaster-recovery.md) | Three failure classes + quarterly drill cadence |
| [docs/runbook/onboarding.md](docs/runbook/onboarding.md) | Bahasa Indonesia operator walkthrough |

## Related projects

| Project | Role | Source |
|---|---|---|
| `auto-inspect-service` | Inference engine (graphflow + YOLO + Anomalib + OCR) — we orchestrate it | `D:\Projects\Indusia-Inspection\auto-inspect-service\` |
| `auto-inspect-edge` | On-prem hardware orchestrator (PLC + Hikrobot camera) — pulls our weights | `D:\Projects\Indusia-Inspection\auto-inspect-edge\` |
| `auto-inspect-engine` | Estimator / transform foundation — service depends on this | `D:\Projects\Indusia-Inspection\auto-inspect-engine\` |
| `label-studio` | Upstream LSF source (Apache-2.0) — we build + vendor the bundle | `D:\Projects\label-studio\` |

## License

Proprietary — Indusia AI. The embedded Label Studio Frontend bundle is Apache-2.0; its license + attribution are preserved at `web/public/lsf/3rdpartylicenses.txt` and surfaced on the About page per Apache 2.0 §4(d).

## Contact

indusiaai@gmail.com
