# Inspection Stability Hardening — Design

> Brainstormed 2026-05-30 with the `ai-visual-inspection-expert` skill as the grounding authority.
> Scope: **software-platform only** (no `auto-inspect-service` / `auto-inspect-edge` source changes).
> Status: Design approved. **Implementation gated behind a Figma redesign phase** (operator decision
> 2026-05-30 — see companion `2026-05-30-figma-stability-redesign.md`). No FE modification until Figma
> frames for the new surfaces exist.

## Problem

Current flow: **BOM list → Golden Sample → PCB Drawing → Auto-Labelling → Training**.

The flow is workable as a *seeding + anomaly cold-start* mechanism, but has structural gaps that cause
false detection and production instability. The core misconception it must not encode: a golden sample
is a **known-good board only — zero defect examples** — so "labelling → training" cannot directly
produce a supervised multi-class defect detector on day one. The correct architecture is **two-track**:
anomaly-on-good live from day one (already wired via `anomalib_roi` / `anomalib_whole_side`), supervised
YOLO accumulating from real operator corrections over time.

## Diagnosis — 7 gaps (ranked by false-call impact), each verified against the codebase

| # | Gap (code-verified) | False-call impact | Severity | Skill reference |
|---|---|---|---|---|
| G1 | Single golden per side; no multi-sample set. `assets` has **no `UNIQUE(project_id, kind)`** so multiple rows already store. | Anomaly baseline from 1 board over-triggers on normal process variation (electrode/land/alloy). | High | §7 / field-playbook §4 — multi-sample good set + averaged multi-frame |
| G2 | `fiducial_strategy` chosen but never verified; no registration-quality gate before training. | Registration drift = every label wrong at once. #1 field false-call source. | High | §7 RCA — verify fiducial contrast → ±5 µm registration |
| G3 | Zero post-deploy monitoring/feedback (`grep drift/feedback/escape` → empty). | Domain shift on board-revision / vendor change → escape rate rises silently. | High | §9 / §3.2 — re-validate+retrain; suspend if mAP drift >~5% |
| G4 | No golden QC (no blur/focus/exposure check in `services/asset/`). | Soft/under-exposed golden silently becomes the anomaly reference → garbage baseline. | Med-High | §7 — averaged multi-frame; lighting before model |
| G5 | No stable held-out eval split (no holdout/seed logic). | Gate-2 metrics not comparable run-to-run → wrong promote decisions. | Med-High | §10 — stable 70/15/15 held-out split |
| G6 | Auto-label confidence not gated; low-confidence regions not flagged to operator. | Rubber-stamped auto-labels pollute training data (resistor/pad confusion). | Med | §5/§10 — hard-negative mining, confusion audit |
| G7 | No accumulating defect library; `labels` is latest-wins per side. | Supervised track never matures — stuck on anomaly forever. | Med | §3 — two-track, supervised accumulative |

**Confirmed healthy:** anomaly-on-good is already a live detector option (`anomalib_roi`, `anomalib_whole_side`
in `data/defect_detector_mapping.yaml` → service nodes via the M4 adapter). The two-track base is reachable;
only the data-flow and guardrails are missing.

## Solution — 3 tiers

### Tier 1 — Input integrity (G1, G2, G4) — highest leverage
- **G1 Multi-sample golden set.** Wizard accepts N golden boards per side; anomaly trainer receives the
  set (Anomalib native good-folder paradigm), not one board. No migration (assets already allows N rows).
- **G2 Registration-quality gate.** Add `opencv-python` (§4-blessed). New `services/asset/registration.py`:
  fiducial-contrast + golden↔drawing alignment-error estimate. Surfaces as a **Gate-1 pre-flight**:
  green ✓ proceed / red ✗ hard-stop with reason. Pure platform.
- **G4 Golden QC.** Laplacian-variance (blur) + histogram (exposure) check **on upload**; flag a soft
  golden before it becomes the anomaly reference.

### Tier 2 — Trust over time (G3, G5)
- **G3 Drift monitor — honest scope split.** Live escape/false-call telemetry needs the edge to report
  back; edge is no-touch in v1 → **deferred to v1.5**. Platform-only NOW: (a) operator-marked feedback
  control ("tandai: defect lolos / overkill") + (b) scheduled re-eval of the promoted model against the
  fixed holdout set → alarm + suggest re-validate when mAP drifts >5% from baseline. No faked telemetry.
- **G5 Stable eval split.** Persist a holdout assignment in our DB (per-label split flag, fixed seed),
  reused across retrains so Gate-2 metrics are comparable.

### Tier 3 — Data maturity (G6, G7)
- **G6 Confidence gating.** Flag low-confidence Gemma prelabel regions distinctly in the LSF task + show
  the count so operators scrutinize rather than rubber-stamp.
- **G7 Defect library.** Move from latest-wins-discard to an accumulating corrected-defect store so the
  supervised YOLO track matures over time.

## Data Integration Map

| Capability | Data source | Exists? | Integration flag |
|---|---|---|---|
| G1 multi-golden store | `assets` (no kind-unique) | yes | Spike: confirm service anomaly-trainer accepts image *set* |
| G1/G2/G4 pixel ops | `opencv-python` | add dep | §4-blessed, not a stack deviation |
| G2 fiducial/registration | golden + drawing assets | stored | Platform-side opencv; no sibling change |
| G3 (a) operator feedback | new table `inspection_feedback` | new | Pure platform |
| G3 (b) drift re-eval | existing `/training/{run}/eval` + holdout | partial | Re-run eval on fixed set |
| G3 live edge telemetry | edge inspection results | **blocked** | v1.5 — edge no-touch |
| G5 stable split | `labels` + new split flag | schema add | Pure platform |
| G7 defect library | `labels` (latest-wins now) | schema/redesign | Pure platform; training uses existing flow |

## New UI surfaces these gaps require (drives the Figma redesign)

| Gap | View affected | New surface |
|---|---|---|
| G1 | WizardView (step 3 golden) | Multi-upload dropzone + per-board thumbnail strip + "set" count |
| G4 | WizardView (step 3) | Per-board QC badge (blur/exposure pass/warn/fail) |
| G2 | Gate1View | Registration pre-flight panel (fiducial contrast + alignment error + hard-stop state) |
| G6 | LabelingView | Low-confidence region highlight + count chip in action strip |
| G5 | SetupEvalView | "Locked test set" indicator (split frozen across retrains) |
| G3a | NEW surface | Operator feedback control to mark escape/overkill on an inspection |
| G3b | ModelsView or new Monitoring card | Drift status (baseline mAP vs latest re-eval) + re-validate CTA |
| G7 | DatasetsView | Accumulating defect-library counts per class |

## Implementation ordering (operator-set 2026-05-30)

1. **Figma redesign FIRST** — design all new surfaces above to parity before touching FE
   (companion plan `2026-05-30-figma-stability-redesign.md`).
2. Backend + data (schema, opencv, registration, QC, drift re-eval, defect library) — can proceed in
   parallel with Figma since it has no UI dependency.
3. FE modification — only after Figma frames exist.

## Feedback loop & model-enrichment lifecycle (added 2026-05-30)

The Feedback screen (S7) is the **curation surface for inspection results returning FROM the HMI**
(`auto-inspect-edge`) INTO the Visual Editor. It is NOT throwaway UI — it is the human gate that turns
real-line outcomes into training data.

### Two-track model lifecycle (per ai-visual-inspection-expert §3/§5/§10)
1. **Cold start (Day 1)** — only golden samples exist (good boards, zero defects). Train **anomaly-on-good**
   (`anomalib_roi` / `anomalib_whole_side`, already wired). Flags deviation-from-good; catches unknowns,
   cannot name them, over-triggers slightly. This is the baseline that goes live.
2. **Production** — real defects appear. Anomaly (or operator) flags a region; the HMI operator marks the
   true verdict. Region crop + true label → a labeled defect example.
3. **Accumulate** — confirmed defects pile up per criterion (missing_component, polarity_flip, solder_short…)
   in the defect library (S8).
4. **Enrich (track 2, supervised)** — once a class has enough real examples (~100+ floor for stability;
   start earlier with synthetic ~400 real + ~1000 generated + focal loss since defects are <1% of
   production), train a per-component **YOLO** for that defect — faster, localizes + names, fewer false calls.
5. **Promote** — retrain promotes ONLY if it clears locked thresholds (mAP 0.80 / F1 macro 0.80 /
   per-comp F1 0.70) at Gate 2, measured against the **locked holdout split** (S5).
6. **Watch** — scheduled re-eval vs the locked holdout (S6) catches drift on new board revisions / vendor
   changes. Anomaly keeps running underneath the whole time for the unknown tail.

Loop: anomaly flags unknowns → HMI operator marks → confirmed defects enrich library → supervised matures
→ Gate-2 promote → push to edge → sharper detection → cleaner feedback → repeat.

### Feedback-ingest architecture (G3 + G7 made concrete)
- **Table `inspection_feedback`**: id, project_id FK, edge_id FK (nullable), train_run_id FK (lineage —
  which deployed model produced the verdict), designator, `model_verdict` CHECK(pass/fail/uncertain),
  `operator_mark` CHECK(confirmed/escape/overkill), `defect_criterion` (nullable, one of the 9), `roi_path`
  + `roi_sha256` (the cropped region image), `status` CHECK(new/curated/promoted/dismissed), inspection_ts,
  created_at. (escape = model passed but defect present — the expensive miss; overkill = model failed but
  actually OK — false call.)
- **Endpoints**: `POST /api/projects/{id}/inspection-feedback` (ingest + ROI upload, bearer-gated),
  `GET /api/projects/{id}/inspection-feedback?status=new` (feeds S7), `PUT /api/inspection-feedback/{fid}`
  (curate/confirm/dismiss), `POST /api/inspection-feedback/{fid}/promote` (convert a confirmed escape into a
  labeled defect example in the library, available to the next supervised retrain).
- **v1 vs v1.5**: in **v1** the ingest endpoint EXISTS and S7 is the engineer's manual review queue (feed
  via UI or a thin script). In **v1.5** the edge is extended to POST each borderline inspection (ROI + verdict
  + operator mark) to the ingest endpoint automatically, authed via an edge API key — same table, same S7,
  now real time. This is the inbound mirror of today's outbound refresh webhook; it does NOT modify the edge
  in v1.

## Anti-placeholder / honesty notes
- G3 live edge telemetry is explicitly v1.5; the v1 deliverable is operator-marked feedback + scheduled
  re-eval against a fixed set. Do not stub a fake live-drift feed.
- The feedback-ingest endpoint is real in v1; only the *automatic edge push* is v1.5. S7 works either way.
- Height-class defects (tombstone, billboard, lifted lead) remain a 2D limit; anomaly-on-good is the
  closest proxy — do not over-promise YOLO 2D.

---

## Implementation Plan

> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution, NEVER substitute placeholders
> for real data sources without explicit user approval. If a data source doesn't exist yet, STOP and ask.

### Goal

Ship the **v1 inspection-feedback loop + enrichment seed**: persist inspection outcomes returning from the
line (HMI/operator marks `escape`/`overkill`/`confirmed`), let an engineer curate them in the existing S7
"Inspection feedback" screen, and **promote** confirmed escapes into a real `defect_examples` library row
(ROI crop + criterion + designator) that the future supervised retrain consumes. Software-platform only —
NO `auto-inspect-edge` / `auto-inspect-service` source changes. Live automatic edge-push stays v1.5; the
ingest endpoint is real now and fed manually/by script.

### Architecture Context (from CLAUDE.md + code research)

- **Migrations** live at repo-root `alembic/versions/` (NOT under `src/`). Next = `0012_inspection_feedback`,
  `down_revision="0011_auth"`. Pattern: `op.create_table` with `postgresql.UUID(as_uuid=True)` PK, FK via
  `sa.ForeignKey("...", ondelete=...)`, CHECK via inline `sa.CheckConstraint("col IN ('a','b')", name="ck_*")`,
  `op.create_index("ix_<t>_<c>", "<t>", [...])`; `downgrade()` mirrors with `op.drop_table`.
- **ORM** `src/indusia_visual_editor/db/models.py`: `Base(DeclarativeBase)`, `Mapped[...]`/`mapped_column`,
  `PG_UUID(as_uuid=True)` PK `default=uuid.uuid4`, FK CASCADE + `index=True`, `JSONB`, `DateTime(timezone=True)`
  `server_default=func.now()`, CHECK enums as `String(16)` + `CheckConstraint` in `__table_args__`
  (match 0011 `users.role`), composite constraints in `__table_args__`, `relationship(back_populates=...)`.
- **Routes** `src/indusia_visual_editor/routes/*.py`: `APIRouter(prefix="/api/...")`; mutations carry
  `dependencies=[Depends(get_current_user)]`, GETs stay public (v1 decision); inject
  `session: AsyncSession = Depends(get_session)`; success path returns `success(data=..., message=...,
  status_code=...)` from `utils/responses.py`; 404/409 raise `HTTPException(status_code=..., detail=...)`
  (main.py handlers build the envelope); `_serialize(row)=Schema.model_validate(row).model_dump(mode="json")`.
  Register the new router in `src/indusia_visual_editor/main.py` next to the others.
- **File upload** mirrors `routes/assets.py` + `services/asset/image_store.py` (sha256 dedup, path
  `<IVE_STORAGE_ROOT>/{project_id}/{kind}/{sha}{ext}`, `AssetTooLargeError`→413). ROI crops use a new
  `services/feedback/roi_store.py save_roi(project_id, file_bytes, filename)->(rel_path, sha256)` writing to
  `{project_id}/feedback_roi/{sha}{ext}` — kept OUT of the `assets` table (ROI ≠ project source asset).
- **Schemas** `src/indusia_visual_editor/schemas/`: request `ConfigDict(extra="ignore")`, response
  `ConfigDict(from_attributes=True)`, `Literal[...]` for closed sets.
- **Backend tests** `tests/routes/*`: per-file `client` (httpx `ASGITransport(app=app)`) + `query_session`
  fixtures, `pytestmark = skipif(not IVE_DATABASE_URL)`; conftest overrides `get_current_user`→synthetic
  engineer; assert `r.json()["status"]` + payload under `["data"]`. `pytest-asyncio` mode auto.
- **FE**: Pinia Composition store `web/src/stores/*.ts` + axios module `web/src/api/*.ts` over `apiClient`
  (baseURL `/api`, unwrap `data.data`); router `web/src/router/index.ts` (`meta.titleKey`, lazy import);
  views are plain roots under the global `AppShell`; **sidebar nav is `web/src/components/layout/AppSidebar.vue`**
  (the Figma nav item `Sb/Feedback` was design-only — FE nav must be added here); i18n `en.json`/`id.json`;
  dev MSW handlers in `web/src/mocks/handlers.ts`. Figma S7 frames: ID `272:2`, EN `279:2`.
- **Inspection logic (ai-visual-inspection-expert):** promote-eligible = `operator_mark=='escape'` (real
  missed defect) AND `defect_criterion` ∈ the 9 (`data/defect_detector_mapping.yaml`) AND `roi_path` present.
  `overkill` = hard-negative, NOT a defect example → promotion rejected in v1 (hard-negative mining is a
  training-side v1.5 concern). The 9 criteria: missing_component, orientation, polarity_flip,
  connector_pin_bending, missing_pin_connector, lifted_pin, wrong_value, misalignment, solder_short.

### Tech Stack

FastAPI 0.121 async + SQLAlchemy 2 async + Alembic + asyncpg + pydantic v2; pytest-asyncio + httpx
ASGITransport. Vue 3.5 + Pinia 2 (Composition) + axios + vue-router + vue-i18n 10 + Tailwind 3 + MSW 2 +
Vitest. structlog `get_logger`. No new runtime deps (opencv is for G2/G4, not this plan).

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Feedback persistence | `inspection_feedback` table | new ORM model + 0012 migration | No | Create (real table) |
| Promote target | `defect_examples` table | new ORM model + 0012 migration | No | Create (real table) |
| ROI crop storage | `IVE_STORAGE_ROOT/{pid}/feedback_roi/` | `services/feedback/roi_store.save_roi` | No | Create (reuses sha256/ext pattern) |
| Bearer gate | `get_current_user` | `services.auth.dependencies` | Yes | Use existing |
| DB session | `get_session` | `db.session` | Yes | Use existing |
| Envelope | `success()` / `HTTPException` | `utils/responses.py` + main handlers | Yes | Use existing |
| Criterion validity | 9 defect criteria | `data/defect_detector_mapping.yaml` keys | Yes | Load + validate in promote |
| FE HTTP | `apiClient` (`/api`, bearer, 401-refresh) | `web/src/api/client.ts` | Yes | Use existing |
| FE feedback calls | new `api/inspectionFeedback.ts` | wraps apiClient | No | Create |
| FE state | new `useInspectionFeedbackStore` | Pinia | No | Create |
| FE screen | `InspectionFeedbackView.vue` | route `/feedback` | No | Create (Figma S7 272:2/279:2) |
| FE nav item | `AppSidebar.vue` WORKSPACE section | — | Partial | Add entry (Figma design exists) |
| Dev mocks | `feedbackDb` + handlers | `web/src/mocks/handlers.ts` | No | Create |
| Live edge push | edge inspection results | — | **OUT (v1.5)** | Do NOT build; ingest endpoint stands ready |

### Phase A — DB models + migration 0012 (backend, no UI)

**Estimated time:** 14 min
**Files:** Modify `src/indusia_visual_editor/db/models.py`; Create `alembic/versions/0012_inspection_feedback.py`; Test `tests/db/test_inspection_feedback_models.py`
**Steps:**
1. Write failing test for InspectionFeedback + DefectExample ORM roundtrip + CHECK rejection (bad `operator_mark`) + project-cascade delete. Expected error: `ImportError: cannot import name 'InspectionFeedback' from indusia_visual_editor.db.models`.
2. Run it (DB-gated), confirm it fails for that reason.
3. Add `InspectionFeedback` (id, project_id FK CASCADE+index, edge_id FK SET NULL nullable, train_run_id FK SET NULL nullable, designator String(32) nullable, model_verdict String(16), operator_mark String(16), defect_criterion String(40) nullable, roi_path Text nullable, roi_sha256 String(64) nullable, status String(16) default 'new', inspection_ts tz nullable, created_at server_default now()) with `__table_args__` CHECK constraints (`ck_inspection_feedback_verdict` pass/fail/uncertain; `ck_..._mark` confirmed/escape/overkill; `ck_..._status` new/curated/promoted/dismissed) + `DefectExample` (id, project_id FK CASCADE+index, source_feedback_id FK SET NULL nullable, designator String(32) nullable, defect_criterion String(40) not null, roi_path Text not null, roi_sha256 String(64) not null, created_at). Add `relationship` back-refs on `Project`.
4. Write migration `0012_inspection_feedback` (down_revision `0011_auth`) creating both tables + indexes; downgrade drops both.
5. Run `alembic upgrade head` then `downgrade -1` then `upgrade head` against dev DB — clean. Run the ORM test, confirm pass.
6. Commit: `feat(fb): inspection_feedback + defect_examples tables (0012)`

**Verification:**
- [ ] `alembic upgrade head` / `downgrade -1` / `upgrade head` cycle clean
- [ ] ORM roundtrip + CHECK rejection + cascade test passes (DB-gated)
- [ ] No placeholder/TODO in new code
- [ ] `black`/`isort`/`flake8` clean on changed files

### Phase B — Pydantic schemas

**Estimated time:** 8 min
**Files:** Create `src/indusia_visual_editor/schemas/inspection_feedback.py`; Test `tests/schemas/test_inspection_feedback_schemas.py`
**Steps:**
1. Write failing test asserting `FeedbackIngest` rejects an out-of-set `operator_mark` and `FeedbackRead.model_validate(orm_row)` works. Expected error: `ModuleNotFoundError: ...schemas.inspection_feedback`.
2. Run, confirm fail.
3. Implement `FeedbackIngest` (extra="ignore"; designator, model_verdict Literal, operator_mark Literal, defect_criterion optional, inspection_ts optional, edge_id/train_run_id optional), `FeedbackCurate` (operator_mark + status Literals), `FeedbackRead` + `DefectExampleRead` (from_attributes).
4. Run tests, confirm pass.
5. Commit: `feat(fb): pydantic schemas for inspection feedback`

**Verification:**
- [ ] `tsc`-equivalent: `mypy`/import clean; schema validation test passes
- [ ] Literals match the table CHECK sets exactly
- [ ] No placeholder/TODO

### Phase C — ROI storage service

**Estimated time:** 8 min
**Files:** Create `src/indusia_visual_editor/services/feedback/__init__.py` + `roi_store.py`; Test `tests/services/feedback/test_roi_store.py`
**Steps:**
1. Write failing test (tmp `IVE_STORAGE_ROOT`): `save_roi` writes bytes, returns `(rel_path, sha256)` with path `{pid}/feedback_roi/{sha}{ext}`, dedups identical bytes. Expected error: `ModuleNotFoundError`.
2. Run, confirm fail.
3. Implement `save_roi(project_id, file_bytes, filename, mime=None)` reusing the hashing/ext/size-cap logic from `image_store` (raise `AssetTooLargeError` over `max_asset_bytes`); return relative path + sha. Add `absolute_roi_path(rel)` helper.
4. Run tests, confirm pass.
5. Commit: `feat(fb): ROI crop storage service`

**Verification:**
- [ ] save_roi writes file + dedups; path layout correct (non-DB test, tmp dir)
- [ ] oversize raises 413-mapped error
- [ ] No placeholder/TODO

### Phase D — Ingest + list endpoints

**Estimated time:** 12 min
**Files:** Create `src/indusia_visual_editor/routes/inspection_feedback.py`; Modify `src/indusia_visual_editor/main.py` (include_router); Test `tests/routes/test_inspection_feedback.py`
**Steps:**
1. Write failing test: `POST /api/projects/{id}/inspection-feedback` (multipart Form fields + optional ROI file) → 201 + envelope + row persisted; `GET /api/projects/{id}/inspection-feedback?status=new` returns only new. Expected error: 404 (route not registered).
2. Run (DB-gated), confirm fail.
3. Implement router: `POST` (bearer-gated; `Form(...)` metadata + optional `UploadFile`; `get_project` 404 guard; if file → `save_roi`; insert row) returns 201 `success`; `GET` (public) lists by optional `status` Query, ordered by `created_at` desc. Register in main.py.
4. Run tests, confirm pass.
5. Commit: `feat(fb): inspection-feedback ingest + list endpoints`

**Verification:**
- [ ] POST persists row (+ ROI when present), 201 envelope; GET filters by status
- [ ] POST requires bearer (401 without — covered by existing middleware test pattern); GET public
- [ ] No placeholder/TODO; flake8 clean

### Phase E — Curate + promote endpoints

**Estimated time:** 12 min
**Files:** Modify `routes/inspection_feedback.py`; Test (extend) `tests/routes/test_inspection_feedback.py`
**Steps:**
1. Write failing test: `PUT /api/inspection-feedback/{fid}` updates status/mark (404 unknown); `POST /api/inspection-feedback/{fid}/promote` on a confirmed **escape** with valid criterion + ROI creates a `DefectExample` + sets status `promoted`; promote on an **overkill** → 409; promote without ROI/criterion → 409. Expected error: 404 (routes absent).
2. Run, confirm fail.
3. Implement `PUT` (bearer; load-or-404; set operator_mark/status; flush/refresh) and `POST .../promote` (bearer; load-or-404; guard mark==escape & defect_criterion ∈ yaml keys & roi_path present else 409; create DefectExample from the row; status='promoted'). Load the 9 criteria from `data/defect_detector_mapping.yaml`.
4. Run tests, confirm pass.
5. Commit: `feat(fb): curate + promote-to-defect-library endpoints`

**Verification:**
- [ ] curate updates + 404; promote creates DefectExample + flips status
- [ ] promote rejects overkill / missing-ROI / invalid-criterion with 409 (inspection-logic gate)
- [ ] No placeholder/TODO; flake8 clean

### Phase F — FE api module

**Estimated time:** 6 min
**Files:** Create `web/src/api/inspectionFeedback.ts`; Test `web/src/api/__tests__/inspectionFeedback.spec.ts` (MSW)
**Steps:**
1. Write failing test: `listFeedback('new')` returns parsed rows from a mocked envelope. Expected error: module not found.
2. Run, confirm fail.
3. Implement typed `FeedbackItem`/`DefectExample` interfaces + `listFeedback(status?)`, `ingestFeedback(projectId, payload, roiFile?)` (FormData), `curateFeedback(fid, body)`, `promoteFeedback(fid)` over `apiClient`, unwrapping `data.data`.
4. Run, confirm pass.
5. Commit: `feat(fb): FE inspectionFeedback api module`

**Verification:**
- [ ] `vue-tsc` clean; api spec passes against MSW
- [ ] Paths are bare (`/projects/.../inspection-feedback`), no double `/api`
- [ ] No placeholder/TODO

### Phase G — FE Pinia store

**Estimated time:** 8 min
**Files:** Create `web/src/stores/inspectionFeedback.ts`; Test `web/src/stores/__tests__/inspectionFeedback.spec.ts`
**Steps:**
1. Write failing test: `fetchAll()` populates items + `newCount`/`escapeCount` getters; `promote(id)` flips that row to promoted. Expected error: store import fails.
2. Run, confirm fail.
3. Implement `useInspectionFeedbackStore` (items, loading, error refs; `newCount`/`escapeCount`/`overkillCount` computed; `fetchAll(status?)`, `curate(id, body)`, `promote(id)` with optimistic update + `extractMessage` error handling mirroring `stores/edges.ts`).
4. Run, confirm pass.
5. Commit: `feat(fb): useInspectionFeedbackStore`

**Verification:**
- [ ] store spec passes (fetch + counts + curate + promote)
- [ ] error path sets `error` via extractMessage
- [ ] No placeholder/TODO

### Phase H — FE view + route + sidebar nav + i18n

**Estimated time:** 14 min

| Phase | Code Deliverable | Design Deliverable | Verification |
|---|---|---|---|
| H | InspectionFeedbackView + route + AppSidebar entry | Figma S7 frames `272:2`(ID)/`279:2`(EN) + §A.6 tokens | vue-tsc + component test + design-token compliance |

**Files:** Create `web/src/views/InspectionFeedbackView.vue`; Modify `web/src/router/index.ts`, `web/src/components/layout/AppSidebar.vue`, `web/src/locales/en.json` + `id.json`; Test `web/src/views/__tests__/InspectionFeedbackView.spec.ts`
**Steps:**
1. Write failing test: view mounts, calls `store.fetchAll` on mount, renders a row per item, clicking "Defect lolos" calls `store.curate(...,{operator_mark:'escape'})`. Expected error: view import fails.
2. Run, confirm fail.
3. Build the view per the S7 Figma (explainer banner + table: time/board/model-verdict pill/note/action chips escape+overkill + resolved pills), using foundation Tailwind tokens, `useI18n` keys under `feedback.*`, fetch in `onMounted`, toasts via `useToastStore`. Add route `{ path:'/feedback', name:'inspection-feedback', component: () => import('@/views/InspectionFeedbackView.vue'), meta:{ titleKey:'nav.feedback' } }`. Add the WORKSPACE nav item (label `nav.feedback`, `to:'/feedback'`, speech-bubble Lucide icon) in `AppSidebar.vue`. Add `nav.feedback` + `feedback.*` keys to en/id.
4. Run tests + `vue-tsc --noEmit` + `eslint`, confirm pass.
5. Commit: `feat(fb): Inspection feedback view + route + sidebar nav`

**Verification:**
- [ ] `vue-tsc --noEmit` + eslint clean
- [ ] View renders rows from `useInspectionFeedbackStore`; escape/overkill actions call store; resolved rows show marked state
- [ ] Sidebar shows "Umpan balik"/"Feedback" under WORKSPACE → navigates to /feedback
- [ ] Only §A.6 tokens (no ad-hoc colors); no placeholder/TODO

### Phase I — MSW dev handlers + build verification

**Estimated time:** 8 min
**Files:** Modify `web/src/mocks/handlers.ts`; Test (none new — verification phase)
**Steps:**
1. Write failing test: store spec run in dev/MSW mode hits the 4 mocked endpoints and returns seeded feedback rows. Expected error: MSW 404 (handlers absent).
2. Run, confirm fail.
3. Add `feedbackDb` (≈6 seed rows: mix of escape/overkill/confirmed, 2 resolved) + `defectExamplesDb` + handlers for POST/GET/PUT/promote mirroring the envelope; promote moves a row + appends a defect example.
4. Run full FE suite + `vite build`; confirm green.
5. Commit: `feat(fb): MSW handlers for inspection feedback`

**Verification:**
- [ ] Full `vitest` suite green; `vite build` passes; `vue-tsc` clean
- [ ] MSW promote/curate mutate the in-memory db consistently
- [ ] No placeholder/TODO

### Explicitly OUT of scope (do NOT build here)

- Live edge push (edge POSTs feedback automatically) — **v1.5**; the ingest endpoint stands ready.
- Supervised-trainer **consumption** of `defect_examples` (assembling them into the YOLO training set sent
  to `auto-inspect-service`) — next milestone (touches the training-start service); promote producing a real
  `DefectExample` row is the honest v1 boundary, not a stub.
- overkill → hard-negative mining; G2 opencv registration; G1 multi-golden training payload; G5 stable split;
  G6 drift re-eval — separate milestones in this same design doc.
