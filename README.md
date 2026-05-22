# Indusia Visual Editor

AI-assisted visual editor untuk PCB inspection — upload BOM + golden sample → Gemma 4 auto-pre-label → human review di Label Studio canvas (embed) → 2-gate approve → training & deploy via existing `auto-inspect-service`. Target user: MI division operator / supervisor.

**Status:** design + plan locked, foundation execution belum mulai.

## Documentation

- [`docs/plans/2026-05-22-visual-editor-mvp.md`](docs/plans/2026-05-22-visual-editor-mvp.md) — single source of truth (design + implementation plan, M0–M14 phased)
- [`docs/specs/label-studio-adoption.md`](docs/specs/label-studio-adoption.md) — LSF embed strategy (active v1)
- [`docs/roadmap/inspection-spec-document-v1.5.md`](docs/roadmap/inspection-spec-document-v1.5.md) — PDF inspection-form parser (deferred to v1.5)

## Related projects

- [`Indusia-Inspection`](https://github.com/alisadikinma/Indusia-Inspection) — existing inspection stack (engine + service + edge) that this visual editor orchestrates
- [`label-studio`](https://github.com/HumanSignal/label-studio) — upstream LSF (Apache-2.0), embedded as React island

## Quick start

(scaffold belum dibuat — M0 phase 0.1 dst)

```powershell
# Backend (FastAPI)
poetry install
poetry run uvicorn indusia_visual_editor.main:app --reload --port 8000

# Frontend (Vue 3 + Vite)
cd web && pnpm install && pnpm dev

# Dev env (Postgres)
docker compose -f docker-compose.dev.yml up -d postgres
```

## License

Proprietary — Indusia AI. Embedded Label Studio Frontend (Apache-2.0) attribution preserved at `web/public/lsf/LICENSE.txt`.
