# Indusia Visual Editor

> Factory-user-driven PCB inspection platform. Take a brand-new PCB from photo to production inspection in **hours, not days** — without writing a single line of YAML or touching the CLI.

---

## What this is

The MI division of a PCB factory hand-inserts through-hole components (electrolytic caps, connectors, headers, DIP ICs, transformers) and runs them through wave-solder. Today **no inspection automation covers this stage** — SMT lines have AOI machines, MI lines don't. Defects (lifted pins, polarity flips, misalignment, missing components, wrong values, solder shorts) are caught by tired operators visually checking each board.

Indusia Visual Editor is the platform that fixes this. A manufacturing engineer who knows zero Python and zero computer vision can:

1. Upload a BOM (Excel/CSV) and a photograph of a known-good "golden" PCB.
2. Watch Gemma 4 auto-detect every component on the board and propose an inspection pipeline.
3. Review the AI-drawn bounding boxes on a labeling canvas — correct mistakes with a click, pick per-region which defects to check for.
4. Approve training (Gate 1), wait while the model trains on the existing `auto-inspect-service` stack.
5. Review evaluation metrics (mAP, per-component F1, sample predictions).
6. Approve production deploy (Gate 2). Weights are pushed to the model registry, edges auto-pull, and the inspection runs on the MI line.
7. Chat with the AI advisor when false-call rates climb: "C4 false-positive 5% di line 3, kenapa?"

Everything happens in a browser. Zero YAML, zero CLI, zero domain expertise required from the factory user.

## Who this is for

| User | What they do |
|---|---|
| **MI line supervisor / production engineer** | Primary. Onboards new PCBs, monitors deploys, handles false-call escalations. |
| **Factory IT / system admin** | Deploys the platform on-prem, manages license, watches health. |
| **Indusia AI engineering team** | Maintains the platform, ships new features, owns the cloud control plane. |

Not for: software developers as a labeling tool (use Label Studio directly), nor for general-purpose computer vision (this is PCB-specific).

## Architecture at a glance

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser — Vue 3 + Pinia + LSF-embedded canvas                    │
│ Dashboard · Wizard · Labeling · Train/Eval · Deploy · Chat       │
└─────────────────────────────┬────────────────────────────────────┘
                              │ HTTPS · REST + SSE · WebSocket
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ indusia-visual-editor — FastAPI service (this repo)              │
│ routes/  project · asset · label · train · deploy · chat · ml    │
│ services/ asset · project · label · llm · inspect_service ·      │
│           deploy · inspect_scope                                  │
│ db/      Postgres 16 (projects, bom_items, labels, train_runs,   │
│          deployments, chat_sessions)                              │
│ storage/ filesystem v1, S3/MinIO v2 (BOM, golden, drawings)      │
└──┬──────────────────┬──────────────────────────┬─────────────────┘
   │ HTTP             │ HTTP                     │ HTTP / WS
   ▼                  ▼                          ▼
┌─────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐
│ Ollama      │  │ auto-inspect-       │  │ auto-inspect-edge       │
│ gemma4:31b  │  │ service (:8001)     │  │ (:8000, on-prem)        │
│ (dedicated  │  │ — graphflow engine, │  │ — PLC, Hikrobot camera, │
│ GPU)        │  │ training, model     │  │ pulls weights via       │
│             │  │ registry (Git+LFS)  │  │ `ais model pull`        │
└─────────────┘  └─────────────────────┘  └─────────────────────────┘
```

Cloud control plane runs at Indusia. On-prem agent at each customer site handles labeling + training + inference; **PCB images never leave the factory** (privacy guarantee — only model weights and metadata reach the cloud).

## Why it works

| Decision | Why |
|---|---|
| Embed Label Studio Frontend as a React island in Vue 3 (Apache-2.0) | LSF already has the canvas we need — bbox + polygon + brush + keypoint + zoom + history + hotkeys + LS-JSON output. Saves ~3 weeks of custom Konva work, zero adapter code. |
| Gemma 4 plays 4 roles: planner, pre-label, runtime defect judge, advisor | One brain across the platform. Dedicated GPU box, 256K context, structured-output validated by pydantic. |
| Reuse `auto-inspect-service` for training + inference unchanged | Existing battle-tested stack with YOLO + Anomalib + OpenVINO + fiducial + OCR. We orchestrate; we don't reinvent. |
| 2 mandatory HITL gates: approve before training + approve before deploy | Production safety. Never auto-approve. |
| User-controlled per-region inspect scope in canvas (not BOM filter) | Trust user judgment. Smart defaults (MI/SMT heuristic) but full override. Inspection criteria picked per-region via `<Choices perRegion>` LSF UI. |

## End-state feature list

- **Project lifecycle**: dashboard, status badges, version history per PCB model
- **BOM parsing**: Excel / CSV with multi-designator row expansion, MI-vs-SMT heuristic classification, fuzzy column matching, transactional persistence
- **Asset management**: golden samples (top + bottom), PCB drawings, fiducial templates; SHA256-dedup, 50MB cap, filesystem v1 / S3 v2
- **AI pre-labeling**: Gemma 4 auto-locates every BOM designator on the golden sample using both image and drawing as priors
- **Labeling canvas**: LSF-embedded, per-region `inspect_scope` (inspected/skipped) + multi-select `defect_criteria`, color-coded by component type, confidence overlay (green/yellow/red), keyboard hotkeys
- **Pipeline planner**: Gemma 4 reads scope+criteria, generates graphflow `config.yaml` + `locations.yaml` + per-component subgraphs targeting `auto-inspect-service` schema
- **Training integration**: Gate 1 preview (dataset stats, AI-suggested epochs/augmentation), trigger via `auto-inspect-service /api/training/start`, SSE progress relay
- **Eval view**: per-component F1 charts, mAP curves, sample prediction grid, comparison vs previous run
- **Promote-to-production**: Gate 2 with eval review, push weights to Git+LFS registry, notify edges to pull
- **Edge orchestration**: per-edge version pin (auto-pull-latest vs locked), webhook refresh, rollback
- **Chat advisor**: slide-out drawer, Gemma sees project history + result metrics + relevant ROI crops, suggests retraining or threshold tweaks
- **Auth + multi-tenant**: JWT email/password, organization isolation, simple roles (admin / engineer / viewer)
- **Production hardening**: Docker Compose + Traefik, Postgres backup, log shipping, deployment runbook

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.10+, FastAPI, pydantic-settings, SQLAlchemy 2 async, Alembic, httpx, sse-starlette |
| Database | PostgreSQL 16 |
| LLM | Ollama `gemma4:31b` on dedicated GPU (20GB, 256K context) |
| Frontend | Vue 3 + Vite + TypeScript + Pinia + Vue Router + Tailwind 3 |
| Labeling canvas | Label Studio Frontend (Apache-2.0) vendored as ES-module bundle |
| Containers | Docker Compose (dev + prod) |
| Reverse proxy | Traefik (auto HTTPS) |
| Testing | pytest + pytest-asyncio + httpx ASGITransport (backend) · Vitest + @vue/test-utils (frontend) |
| Code style | black + isort + flake8 (Python) · eslint + prettier (Vue) |

## Repository layout

```
indusia-visual-editor/
├── src/indusia_visual_editor/   FastAPI service — routes, services, db, schemas
├── tests/                       pytest suite + fixtures + spike investigations
├── web/                         Vue 3 SPA (dashboard, wizard, labeling, train, deploy, chat)
├── docs/
│   ├── plans/                   phased implementation plans (gaspol-plan output)
│   ├── specs/                   technical specs (LSF adoption, graphflow schema, design)
│   ├── roadmap/                 deferred-to-v1.5+ designs
│   └── archive/                 superseded designs (kept for traceability)
├── alembic/                     DB migrations
├── data/                        committed YAML data (taxonomy, detector mapping)
├── docker-compose.dev.yml       dev environment
├── pyproject.toml               Poetry project
└── CLAUDE.md                    project memory — read FIRST every session
```

## Quick start (development)

Prerequisites: Node 24 (via nvm-windows), Python 3.10+, Poetry 2.x, Docker Desktop, an Ollama instance running `gemma4:31b`.

```powershell
# Backend
poetry install
poetry run uvicorn indusia_visual_editor.main:app --reload --host 0.0.0.0 --port 8002
# → http://localhost:8002/health

# Frontend (after Phase 0.3 lands)
cd web
pnpm install
pnpm dev
# → http://localhost:5173

# Database + Ollama + sibling inspection stack (after Phase 0.4 lands)
docker compose -f docker-compose.dev.yml up -d postgres ollama

# Run all tests
poetry run pytest -v          # backend
cd web && pnpm test           # frontend
```

The LSF bundle is built once from the upstream `D:\Projects\label-studio` repo and vendored into `web/public/lsf/` — see [`docs/specs/lsf-build.md`](docs/specs/lsf-build.md) for the verified build procedure.

## Quick start (factory user — post-deploy)

1. Open the platform in Chrome / Edge at the URL your IT team provided.
2. Sign in with email + password.
3. Click **New Project** — name it after the PCB model code from your customer (e.g. `NV80-017542-0501`).
4. Upload `BOM.xlsx` → review the parsed component table.
5. Upload `golden_top.jpg` and `golden_bottom.jpg`. Optionally upload the PCB drawing.
6. Open the labeling canvas — Gemma 4 will have auto-placed bounding boxes on every component it found. Review them, fix any mistakes.
7. For each component you want to inspect, pick **inspect_scope = inspected** and tick the defect criteria you care about (missing, polarity, lifted pin, etc.). Skip the ones you don't.
8. Click **🤖 Build inspection pipeline** → review Gemma's plan → **Start Training** (Gate 1).
9. Wait for training to finish (~10-30 min for small boards, longer for complex ones).
10. Review the evaluation metrics → **Promote to Production** (Gate 2).
11. The inspection runs on your MI line. The chat drawer is there if false calls climb.

## Status

**Active development.** Following the milestone roadmap in [`docs/plans/2026-05-22-visual-editor-mvp.md`](docs/plans/2026-05-22-visual-editor-mvp.md):

| Phase | Status |
|---|---|
| Design + plan + adoption specs | ✅ Done |
| Phase 0.5 — LSF build verification spike | ✅ Done |
| Phase 0.1 — Backend FastAPI scaffold + /health | ✅ Done |
| Phase 0.2 — graphflow config.yaml schema spike | ✅ Done |
| Phase 0.3 — Frontend Vue 3 scaffold | ⏳ Pending |
| Phase 0.4 — Docker Compose dev env | ⏳ Pending |
| M1 — Project + Asset CRUD + Dashboard | ⏳ Pending |
| M2 — BOM parser + classifier + preview | ⏳ Pending |
| M3 — LLM client foundation | ⏳ Pending |
| M4 — Pipeline planner adapter | ⏳ Roadmap |
| M5 — Pre-label assistant | ⏳ Roadmap |
| M6 — Labeling canvas (LSF embed) | ⏳ Roadmap |
| M7 — Training integration + SSE | ⏳ Roadmap |
| M8 — Gate 1 (training approval) | ⏳ Roadmap |
| M9 — Eval metrics view | ⏳ Roadmap |
| M10 — Gate 2 + promote-to-production | ⏳ Roadmap |
| M11 — Edge notification + version pin | ⏳ Roadmap |
| M12 — Chat advisor | ⏳ Roadmap |
| M13 — Auth + multi-user | ⏳ Roadmap |
| M14 — Polish + production deploy | ⏳ Roadmap |

Refer to [CLAUDE.md](CLAUDE.md) for the authoritative current-state inventory (routes built, hooks available, tables existing) — that file is updated every phase, this README describes the eventual product.

## Documentation map

| Doc | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Project memory — current state, conventions, anti-hallucination rules. **Read first.** |
| [docs/plans/2026-05-22-visual-editor-mvp.md](docs/plans/2026-05-22-visual-editor-mvp.md) | Authoritative milestone plan (M0–M14) with per-phase steps |
| [docs/specs/label-studio-adoption.md](docs/specs/label-studio-adoption.md) | LSF embedding strategy + corrected build commands |
| [docs/specs/lsf-build.md](docs/specs/lsf-build.md) | Verified LSF build procedure with artifact inventory |
| [docs/specs/graphflow-config-schema.md](docs/specs/graphflow-config-schema.md) | auto-inspect-service config.yaml + locations.yaml schema reference |
| [docs/roadmap/inspection-spec-document-v1.5.md](docs/roadmap/inspection-spec-document-v1.5.md) | PDF inspection-form parser (deferred to v1.5) |

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

For questions about the platform: indusiaai@gmail.com.
