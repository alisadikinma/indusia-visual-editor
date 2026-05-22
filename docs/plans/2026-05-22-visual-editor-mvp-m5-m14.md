# Indusia Visual Editor — M5–M14 Detailed Breakdown

> **For Claude:** REQUIRED SKILL: Use `gaspol-execute` to implement this plan.
> **CRITICAL:** This plan specifies real integrations. During execution,
> NEVER substitute placeholders for real data sources without explicit
> user approval. If a data source doesn't exist yet, STOP and ask.

> Companion to [`2026-05-22-visual-editor-mvp.md`](./2026-05-22-visual-editor-mvp.md) which contains M0–M4 detail. M0–M4 are SHIPPED (149 backend + 9 frontend tests pass on `origin/main`). This file expands the M5–M14 roadmap entries into executable sub-phases per gaspol-plan discipline.

## Goal

Take the MVP from "BOM + golden image → graphflow YAML written to disk" (M4 end state) all the way to "production-deployed PCB inspection running on the MI line with HITL gates, eval, chat advisor, multi-user auth, and prod-grade observability." Each milestone is broken into TDD-disciplined 2–15-minute phases. Cross-milestone architecture decisions (REST vs subprocess for `ais model push`, structured-logging fields, LSF embed strategy) are captured inline as ADRs.

## Architecture Context (from CLAUDE.md + M0–M4 shipped)

| Existing artifact | Use case for M5+ |
|---|---|
| `services/llm/client.OllamaClient` + `services/llm/planner` | M5 pre-label assistant reuses the structured-output pattern; M12 advisor extends with streaming |
| `services/llm/schemas.PreLabeledRegion` (Phase 3.2) | Already the wire format for M5 output |
| `services/inspect_scope.derive_inspect_scope` (Phase 2.2c) | M6 canvas submit hits this on save — already shipped |
| `services/adapter.compose_from_project` (Phase 4.5) | M6 canvas submit chains into this; M7 reads its output |
| `IVE_MODELS_ROOT` filesystem path | M7 training POST + M10 promote both read from here |
| `proposed_pipelines` + `bom_items` + `adapt_runs` tables | M6 labels link back; M7 train_runs links forward |
| LSF built artifact at `D:\Projects\label-studio\web\dist\libs\editor\` | M6 vendoring source (per `docs/specs/lsf-build.md`) |
| `auto-inspect-service` at port 8001 with `/api/training/start`, `/api/models/{name}/load`, `ais model push` CLI | M7 + M10 are HTTP/subprocess clients against this — never modify the sibling repo |
| `auto-inspect-edge` at port 8000 with `/api/models/refresh-cache` | M11 calls this via webhook |
| Canonical `{status, message, data}` envelope + `HTTPException` handler | All M5–M14 routes inherit this |
| Vue 3 + Pinia + Tailwind + `web/src/api/client.ts` | M5–M13 frontend pieces extend these |

## Cross-cutting ADRs locked in M5–M14

| ADR | Decision | Rejected alternatives |
|---|---|---|
| **M5 prompt context** | Pre-label sends golden + drawing + BOM as a SINGLE multimodal Gemma call, not two separate passes | Two passes (BOM-only then refinement) — doubles latency, adds adapter complexity |
| **M6 LSF integration** | LSF mounted as React 18 island via `instanceOptions.reactVersion: 'v18'` in a Vue 3 wrapper; ML Backend protocol DEFERRED to v1.5 (predictions baked into task JSON) | Fork LSF (violates §10); custom Konva canvas (3+ weeks rework); ML Backend in v1 (untested, adds runtime hop) |
| **M7 training trigger** | `auto-inspect-service /api/training/start` via httpx + SSE relay; subprocess to `ais` CLI is M10-only | Subprocess (race conditions, harder to cancel); shared FS poll (eventual consistency pain) |
| **M10 promote-to-prod** | Subprocess `ais model push` because the registry interface is Git+LFS — no REST endpoint exists in `auto-inspect-service` for it | REST (would require modifying sibling repo per §3); manual Git+LFS commands (auth + LFS quota error-prone) |
| **M11 edge notify** | Outbound webhook + retry-with-backoff; edges register themselves once via REST | Polling (waste); push-only without retry (drops on edge reboot) |
| **M12 chat context** | Last 20 turns + project summary + 3 most-recent ROI crops as base64; truncate aggressively at 200K tokens (Gemma 4 has 256K) | Full history (cost explodes); RAG (overkill for solo-user chat) |
| **M13 auth** | JWT bearer in `Authorization: Bearer <token>` header, refresh via long-lived refresh token in HttpOnly cookie; bcrypt for password storage; no OAuth in v1 | Cookie-only sessions (CSRF surface); OAuth (over-engineered for on-prem single-tenant); plaintext or SHA256 password (illegal) |
| **M14 reverse proxy** | Traefik with file-based dynamic config (NOT k8s ingress) + Let's Encrypt; staging + prod separate compose stacks | Caddy (smaller community), nginx (manual cert rotation), k8s (CLAUDE.md §4 forbids it) |

---

## M5 — Pre-label assistant (auto-labels ALL BOM designators)

### Goal

Given a project's BOM + golden_top + optional drawing, call Gemma 4 to emit a `PreLabeledRegion` for every designator the model can locate on the board. Bake predictions into the LSF task JSON served to the canvas (so the user opens a board with bounding boxes already drawn). Two-image conditioning (golden + drawing) is the key — drawing acts as a spatial prior even when components are partially occluded in the golden image.

### Architecture Context

- `services/llm/planner.py` (Phase 3.3) is the structural template — same pydantic structured-output discipline.
- `services/llm/schemas.PreLabeledRegion` (Phase 3.2) is already the wire format.
- `Asset` rows of `kind=AssetKind.GOLDEN_TOP` and `kind=AssetKind.DRAWING` are pulled via `services/asset/image_store.absolute_path`.
- BOM list comes from `bom_items` table; only designators where `inspect_scope IN ('pending','inspected')` are candidates.
- New table `pre_labels` persists the latest set per (project_id, side); M6 canvas reads it as the task `predictions[]` array.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Pre-label call | Ollama via OllamaClient | `services/llm/client.OllamaClient.generate` | Yes | Use existing |
| Golden + drawing bytes | `Asset` rows + `absolute_path` | `services/asset/image_store` | Yes | Use existing |
| BOM context | `bom_items` table | SQLAlchemy `select(BomItem)` | Yes | Use existing |
| `PreLabeledRegion` schema | `services/llm/schemas.PreLabeledRegion` | direct import | Yes | Use existing |
| Pre-label prompt | `services/llm/prompts/prelabel.md` | new file | No | Create new |
| `services/llm/prelabel.py` (orchestrator) | composes above | new module | No | Create new |
| `pre_labels` table | new Alembic migration `0004_pre_labels.py` | new SQLAlchemy `PreLabel` model | No | Create new |
| `POST /api/projects/{id}/llm/prelabel` + GET | new `routes/llm.py` additions | new endpoints | No | Create new |

### Phase 5.1: Pre-label prompt + orchestrator skeleton

**Estimated time:** 12 min

**Files:**
- Create: `src/indusia_visual_editor/services/llm/prompts/prelabel.md`
- Create: `src/indusia_visual_editor/services/llm/prelabel.py`
- Test: `tests/services/llm/test_prelabel.py`

**Steps:**
1. Write failing test for `prelabel_designators(client, model, bom_designators, golden_image, drawing_image, side) -> list[PreLabeledRegion]`. Expected error: `ImportError`.
2. Run, see fail (skip the real-Ollama branch via `IVE_OLLAMA_INTEGRATION` gate).
3. Author `prompts/prelabel.md` system prompt: explains spatial layout cues, drawing-as-prior, normalized bbox format, side semantics, anti-hallucination guard (return empty array if golden unreadable).
4. Implement `prelabel.py::prelabel_designators` — render prompt + BOM list as JSON + attach 1–2 base64 images + `format=list[PreLabeledRegion].model_json_schema()`. Parse via pydantic.
5. Add tests with fake `_LlmClientProto` double: returns crafted JSON for 3 designators, asserts roundtrip, asserts drawing-image absence still works.
6. Test invalid response → `LlmValidationError`.
7. Commit: `feat(llm): pre-label assistant orchestrator with golden + drawing prior`

**Verification:**
- [ ] 4+ mock tests pass (no real Ollama needed)
- [ ] Drawing argument optional; absence does not crash
- [ ] Output array validates 100% against `list[PreLabeledRegion]`
- [ ] `LlmValidationError` raised on schema violation
- [ ] No placeholder/TODO comments

### Phase 5.2: `pre_labels` table + migration

**Estimated time:** 8 min

**Files:**
- Create: `alembic/versions/0004_pre_labels.py`
- Modify: `src/indusia_visual_editor/db/models.py` (add `PreLabel` model)
- Test: `tests/test_db_models.py` (add 1 case)

**Steps:**
1. Write failing test asserting `PreLabel` row insert + retrieval via `select(PreLabel)`. Expected: `ImportError: cannot import name 'PreLabel'`.
2. Run, see fail.
3. Author migration: `pre_labels(id UUID PK, project_id UUID FK CASCADE, side TEXT CHECK in ('top','bottom'), regions_json JSONB, created_at TIMESTAMPTZ default now(), UNIQUE(project_id, side))`. Latest-wins per side. Index on project_id.
4. Add `PreLabel` SQLAlchemy model with relationship `Project.pre_labels` (cascade-delete).
5. Apply migration: `poetry run alembic upgrade head`.
6. Run tests, confirm GREEN.
7. Commit: `feat(db): pre_labels table — latest pre-label set per project/side`

**Verification:**
- [ ] Alembic downgrade→upgrade cycle clean
- [ ] UNIQUE(project_id, side) enforced (test inserts duplicate and asserts IntegrityError)
- [ ] Cascade-delete from Project verified
- [ ] No placeholder/TODO

### Phase 5.3: Pre-label route + persistence + envelope

**Estimated time:** 15 min

**Files:**
- Create: `src/indusia_visual_editor/schemas/prelabel.py` (`PreLabelRunRead`)
- Modify: `src/indusia_visual_editor/routes/llm.py` (add `/prelabel` endpoints)
- Test: `tests/routes/test_prelabel.py`

**Steps:**
1. Write failing test `test_post_prelabel_persists_regions_with_correct_side`. Expected: 404.
2. Run, see fail.
3. Implement `POST /api/projects/{id}/llm/prelabel?side=top|bottom`:
   - Load BOM, golden_<side>, drawing assets.
   - Call `prelabel_designators` with monkeypatched fake OllamaClient factory (mirror `set_llm_client_factory` pattern from Phase 3.4).
   - UPSERT into `pre_labels` (latest-wins per side).
   - 201 envelope with `PreLabelRunRead`.
4. 422 if golden_<side> missing. 502 on `LlmError`. No row persisted on failure.
5. `GET /api/projects/{id}/llm/prelabel?side=top|bottom` → 200 latest or 404.
6. 5 route tests: happy path, 422 no-golden, 502 on bad JSON, GET latest, GET 404.
7. Commit: `feat(llm): /api/projects/{id}/llm/prelabel route + persistence`

**Verification:**
- [ ] 5 tests pass
- [ ] UPSERT semantics: re-running replaces (not duplicates) the row
- [ ] 502 leaves no row
- [ ] Side query param validated (422 on unknown literal)
- [ ] No placeholder/TODO

### Phase 5.4: Frontend "Build pre-labels" trigger in Wizard step 2

**Estimated time:** 12 min

**Files:**
- Create: `web/src/api/prelabel.ts`
- Modify: `web/src/views/ProjectWizard.vue` (add Step 2 panel)
- Modify: `web/src/stores/wizard.ts` (add `runPreLabel(side)` action)
- Test: `web/src/__tests__/PreLabelPanel.spec.ts` (new)

**Design deliverable:** invoke `gaspol-design` for the step-2 panel (loading state, success badge, retry button, error envelope display).

**Steps:**
1. Write failing Vitest spec for `PreLabelPanel.vue` rendering loading/success/error states. Expected: `Cannot find name 'PreLabelPanel'`.
2. Run, see fail.
3. Implement `api/prelabel.ts` with `runPreLabel(projectId, side)` + `getPreLabel(projectId, side)`.
4. Extend `wizard.ts` store with `runPreLabel` action; tracks per-side `loading`, `regions`, `error`.
5. Implement `PreLabelPanel.vue` — button per side, status indicator, region count, "Re-run" affordance.
6. Wire into `ProjectWizard.vue` Step 2 (the step indicator from Phase 2.3).
7. Run Vitest + manual smoke. Commit.

**Verification:**
- [ ] 3+ Vitest tests pass (loading, success with N regions, error)
- [ ] Loading state shows spinner; success shows region count; error shows envelope `message`
- [ ] Bahasa Indonesia copy throughout
- [ ] `console.log` only inside `if (import.meta.env.DEV)`

---

## M6 — Labeling canvas (LSF embed + per-region scope/criteria UX)

### Goal

User opens a labeled board with `predictions[]` already filled in by M5. Per region they pick `inspect_scope` (inspected/skipped) and a multi-select `defect_criteria` list. On submit, the LSF JSON flows through `derive_inspect_scope` (Phase 2.2c — shipped) → updates `bom_items` → frees M7 training to run. The canvas is the user's primary touchpoint with the platform; everything before this is preparation.

### Architecture Context

- LSF artifact source: `D:\Projects\label-studio\web\dist\libs\editor\` (rebuild per `docs/specs/lsf-build.md`).
- LSF integration boundary documented in CLAUDE.md §10. **Do NOT fork LSF, do NOT modify upstream code.**
- ML Backend protocol DEFERRED to v1.5 — predictions are baked into the task JSON (Phase 5.3 already persists them; this milestone fetches + injects).
- `derive_inspect_scope` (Phase 2.2c) is the post-submit translator — DO NOT reimplement.

### ADR (locked at M6 start)

**LSF mounts as a React 18 island inside a Vue 3 wrapper.** A single Vue component `LSFEmbed.vue` calls `window.LabelStudio(divEl, instanceOptions)` after the bundle loads. `reactVersion: 'v18'` is required (LSF defaults to 17 otherwise). Communication: Vue passes config + task in props; LSF emits onSubmit/onUpdate via callbacks → store actions. Tested as one functional flow, not as isolated React unit tests.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Pre-label predictions for task | `pre_labels` table | `GET /api/projects/{id}/llm/prelabel` (Phase 5.3) | Yes (after M5) | Use existing |
| Golden image bytes | `Asset` `GOLDEN_TOP/BOTTOM` + `absolute_path` | existing | Yes | Use existing |
| BOM designator list (for `<Label>` set) | `bom_items` table | existing | Yes | Use existing |
| Submit handler | `derive_inspect_scope` → `bom_items` writes + persist `labels` row | new route uses existing service | Partial | New route, existing service |
| LSF bundle | `D:\Projects\label-studio\web\dist\libs\editor\` | filesystem copy at build time | Yes (upstream verified) | Vendor in repo |
| `labels` table | new Alembic migration `0005_labels.py` | new SQLAlchemy `Label` model | No | Create new |
| `POST /api/projects/{id}/labels?side=` | new route | new file | No | Create new |
| `GET /api/projects/{id}/labels/task?side=` | new route emits LSF task JSON | new file | No | Create new |
| `LSFEmbed.vue` (React island wrapper) | bundled LSF + window.LabelStudio | new Vue component | No | Create new |
| `LabelingView.vue` (canvas page) | composes LSFEmbed + side selector + save status | new Vue view | No | Create new |
| Wizard step 3 link to LabelingView | new route `/projects/:id/labeling` | Vue Router + ProjectWizard | No | Wire new route |

### Phase 6.1: Vendor LSF bundle into repo

**Estimated time:** 10 min

**Files:**
- Create: `web/public/lsf/main.js` (copied from upstream `dist/libs/editor/main.js`)
- Create: `web/public/lsf/main.css` (and any sibling assets — fonts/, chunks/, wasm/)
- Create: `scripts/vendor-lsf.ps1` (idempotent copy + sha256 manifest)
- Test: `tests/spike/test_lsf_artifact.py` (assert files present + minimum sizes)

**Steps:**
1. Write failing test asserting `web/public/lsf/main.js` exists and is > 100KB. Expected: `AssertionError` or `FileNotFoundError`.
2. Run, see fail.
3. Run `MODE=standalone yarn nx run editor:build:production` in `D:\Projects\label-studio\web\` if the artifact isn't fresh; verify by checking `dist/libs/editor/` mtime against the upstream HEAD.
4. Author `scripts/vendor-lsf.ps1` that mirrors the dist tree into `web/public/lsf/`, recording sha256 of each file to a manifest. Idempotent — second run is a no-op if hashes match.
5. Run the script. Verify `web/public/lsf/main.js`, `main.css`, fonts, chunks, WASM all present.
6. Run tests, confirm GREEN.
7. Commit: `feat(lsf): vendor Label Studio Frontend bundle from upstream`

**Verification:**
- [ ] `web/public/lsf/main.js` exists, > 100KB
- [ ] `web/public/lsf/main.css` exists
- [ ] Vendor script is idempotent (verified by running twice)
- [ ] Manifest file lists each artifact + sha256
- [ ] No source-map files committed
- [ ] No demo media or upstream test fixtures bundled

### Phase 6.2: `labels` DB table + migration

**Estimated time:** 8 min

**Files:**
- Create: `alembic/versions/0005_labels.py`
- Modify: `src/indusia_visual_editor/db/models.py` (add `Label` model)
- Test: `tests/test_db_models.py` (add 1 case)

**Steps:**
1. Write failing test `test_label_row_insert_and_unique_per_side_version`. Expected: `ImportError: cannot import name 'Label'`.
2. Run, see fail.
3. Author migration: `labels(id UUID PK, project_id UUID FK CASCADE, side TEXT CHECK in ('top','bottom'), version INT, ls_json JSONB, snapshot_at TIMESTAMPTZ default now(), UNIQUE(project_id, side, version))`. Index on (project_id, side).
4. Add `Label` SQLAlchemy model with relationship `Project.labels` (cascade-delete).
5. Apply migration. Run tests.
6. Commit: `feat(db): labels table — versioned LSF annotation per project/side`

**Verification:**
- [ ] Alembic downgrade→upgrade cycle clean
- [ ] UNIQUE(project_id, side, version) enforced
- [ ] Cascade-delete from Project verified
- [ ] No placeholder/TODO

### Phase 6.3: GET task + POST submit routes

**Estimated time:** 18 min

**Files:**
- Create: `src/indusia_visual_editor/schemas/labels.py`
- Create: `src/indusia_visual_editor/routes/labels.py`
- Modify: `src/indusia_visual_editor/main.py` (include router)
- Test: `tests/routes/test_labels.py`

**Steps:**
1. Write failing test `test_get_task_returns_lsf_task_json_with_predictions`. Expected: 404.
2. Run, see fail.
3. Implement `GET /api/projects/{id}/labels/task?side=top|bottom`:
   - Load `Asset` `GOLDEN_<SIDE>`, `bom_items` for project, latest `PreLabel` row.
   - Build LSF config XML on the fly (one `<Label>` per designator, color from `component_type`; `<Choices perRegion>` for inspect_scope + defect_criteria).
   - Build LSF task JSON: `data: {image: <signed URL>}, predictions: [pre_label_regions_converted_to_ls_json], annotations: []`.
   - 422 if golden_<side> missing or no BOM rows.
4. Implement `POST /api/projects/{id}/labels?side=top|bottom`:
   - Body: `{ls_json: {...full annotation result list...}}`.
   - Validate via `LSAnnotation` pydantic (already shipped Phase 2.2c).
   - Call `derive_inspect_scope` (existing). Apply updates: write back to `bom_items` (`inspect_scope`, `detector_presets` via JSONB merge or new column).
   - Compute next `version` for (project_id, side). INSERT `Label` row with `ls_json`.
   - 201 envelope with row.
5. 7 tests: GET happy path with predictions, GET 422 missing golden, GET 422 no BOM, POST happy path persists + updates BOM, POST 422 invalid annotation, POST version increment, POST `UnknownDefectCriterion` → 422 (typed exception from derive).
6. Commit: `feat(labels): GET task + POST submit routes with derive_inspect_scope wiring`

**Verification:**
- [ ] 7 route tests pass against real Postgres
- [ ] Task JSON shape validated by parsing back through LSF (Phase 6.5 verifies)
- [ ] `derive_inspect_scope` outputs persist to `bom_items` (test asserts column writes)
- [ ] No double-persistence (POST is atomic — labels INSERT + bom_items UPDATE in same session)
- [ ] No placeholder/TODO

### Phase 6.4: `LSFEmbed.vue` React-island wrapper

**Estimated time:** 18 min

**Files:**
- Create: `web/src/components/LSFEmbed.vue`
- Modify: `web/index.html` (add LSF stylesheet + script tags pointing at `/lsf/`)
- Test: `web/src/__tests__/LSFEmbed.spec.ts`

**Design deliverable:** invoke `gaspol-design` for loading skeleton, save status indicator, and error envelope display matching `docs/design/dashboard-tokens.md`.

**Steps:**
1. Write failing Vitest spec that mounts `LSFEmbed` with mocked `window.LabelStudio`, asserts the constructor is called with `reactVersion: 'v18'`. Expected: `Cannot find name 'LSFEmbed'`.
2. Run, see fail.
3. Modify `web/index.html` to inject `<link rel="stylesheet" href="/lsf/main.css">` + `<script type="module" src="/lsf/main.js">`.
4. Implement `LSFEmbed.vue`: takes `config: string` + `task: object` + emits `onSubmit(annotation)` and `onUpdate(annotation)`. Mounts on `<div ref="hostRef">`. `onMounted` waits for `window.LabelStudio` (poll up to 5s; emit error if missing).
5. Wire `instanceOptions`: `reactVersion: 'v18'`, `config`, `task`, `onLabelStudioLoad`, `onSubmitAnnotation: (ls, ann) => emit('submit', ann)`, etc.
6. Vitest with `vi.stubGlobal('LabelStudio', mockConstructor)` — assert mount, assert callbacks wire, assert unmount calls LSF teardown.
7. Commit: `feat(canvas): LSFEmbed Vue wrapper around Label Studio React island`

**Verification:**
- [ ] 3+ Vitest tests pass
- [ ] `window.LabelStudio` polled for, error envelope emitted if missing after 5s
- [ ] `reactVersion: 'v18'` explicitly set
- [ ] Component cleans up on unmount (no console warnings)
- [ ] No placeholder/TODO

### Phase 6.5: `LabelingView.vue` page + wizard step 3 wiring

**Estimated time:** 18 min

**Files:**
- Create: `web/src/views/LabelingView.vue`
- Create: `web/src/api/labels.ts`
- Create: `web/src/stores/labels.ts`
- Modify: `web/src/router.ts` (add `/projects/:id/labeling` route)
- Modify: `web/src/views/ProjectWizard.vue` (Step 3 link)
- Test: `web/src/__tests__/LabelingView.spec.ts`

**Design deliverable:** `gaspol-design` for the side-toggle (top/bottom), save indicator, and "skipped-region opacity dim" CSS overlay per plan §M6.

**Steps:**
1. Write failing Vitest spec mounting `LabelingView`, expecting it to GET the task JSON and pass `task` + `config` to a mocked `LSFEmbed`. Expected: `Cannot find name 'LabelingView'`.
2. Run, see fail.
3. Implement `api/labels.ts`: `getTask(projectId, side)`, `submitLabels(projectId, side, lsJson)`.
4. Implement `stores/labels.ts`: state `{config, task, saving, error, version}`; actions `fetchTask`, `submit`.
5. Implement `LabelingView.vue`: side toggle (top/bottom), embedded `LSFEmbed`, save-status indicator, submit button.
6. Add visual overlay: CSS rule that dims regions where the user picked `inspect_scope=skipped` (LSF emits `region.classifications` on update — use a watcher).
7. Wire into router + ProjectWizard Step 3.
8. Run Vitest + manual smoke (boot dev server, open the route).
9. Commit: `feat(canvas): LabelingView wires LSFEmbed to backend task + submit endpoints`

**Verification:**
- [ ] 3+ Vitest tests pass
- [ ] Side toggle re-fetches task on change
- [ ] Submit success shows the new version in the save indicator
- [ ] Skipped-region dim overlay verified in manual smoke
- [ ] Bahasa Indonesia copy throughout
- [ ] No `console.log` outside `import.meta.env.DEV`

### Phase 6.6: Backend → bom_items column writes

**Estimated time:** 12 min

**Files:**
- Modify: `src/indusia_visual_editor/db/models.py` (add `detector_presets` JSONB column to `BomItem`)
- Create: `alembic/versions/0006_bom_items_detector_presets.py`
- Modify: `src/indusia_visual_editor/routes/labels.py` (write back during POST)
- Test: `tests/routes/test_labels.py` (extend with assertion)

**Steps:**
1. Write failing test asserting POST `/labels` updates `bom_items.detector_presets` for the matching designators. Expected: `AttributeError: BomItem has no attribute 'detector_presets'`.
2. Run, see fail.
3. Migration adds nullable JSONB `detector_presets` column to `bom_items`.
4. Add `BomItem.detector_presets` Mapped column.
5. Modify POST `/labels` handler: after `derive_inspect_scope`, for each `BomItemUpdate` write `inspect_scope`, `detector_presets`, `scope_mode` to the corresponding `bom_items` row.
6. Apply migration, run tests.
7. Commit: `feat(labels): persist derived detector_presets onto bom_items rows`

**Verification:**
- [ ] Migration downgrade→upgrade clean (column drop must work; rows with non-null JSONB are dropped cleanly)
- [ ] Test asserts updated column on the right designator
- [ ] M4 adapter now picks up real `detector_presets` instead of only the in-flight LSAnnotation
- [ ] No placeholder/TODO

---

## M7 — Training integration (auto-inspect-service handshake + SSE relay)

### Goal

User clicks "Start Training" (Gate 1 — comes in M8). Backend POSTs the model dir path to `auto-inspect-service /api/training/start`, gets back a `job_id`, opens an SSE stream against the service for progress events, and relays them to the frontend via our own SSE endpoint. Final metrics + status persist to `train_runs` table.

### ADR

**HTTP + SSE relay, not subprocess.** `auto-inspect-service` already exposes `/api/training/start` with an SSE response (verified during M0 Phase 0.2 spike). Our backend is a thin proxy: forwards the request, propagates the SSE stream byte-for-byte (with field re-tagging for our envelope), persists the terminal event. This keeps the sibling repo untouched and avoids subprocess lifecycle complexity.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Model dir to train | `adapt_runs.model_dir` (latest per project) | SQLAlchemy `select` | Yes | Use existing |
| Training trigger | `auto-inspect-service /api/training/start` | httpx async client | No | New `services/inspect_service/training_client.py` |
| SSE relay | sse-starlette `EventSourceResponse` | new endpoint | No | New route in `routes/training.py` |
| Run persistence | `train_runs` table | new model + migration | No | Create new |
| Final metrics | terminal SSE event body | inline JSON parse | n/a | Inline |
| Frontend `EventSource` consumer | `web/src/api/training.ts` | new module | No | Create new |

### Phase 7.1: `services/inspect_service/training_client.py` + SSE primitive tests

**Estimated time:** 15 min

**Files:**
- Create: `src/indusia_visual_editor/services/inspect_service/__init__.py`
- Create: `src/indusia_visual_editor/services/inspect_service/training_client.py`
- Create: `src/indusia_visual_editor/services/inspect_service/exceptions.py`
- Test: `tests/services/inspect_service/test_training_client.py`

**Steps:**
1. Write failing test `test_start_training_returns_job_id_from_service`. Expected: `ImportError`.
2. Run, see fail.
3. Implement `TrainingClient(base_url, timeout).start_training(model_dir: str) -> str`: POST `/api/training/start` with `{model_dir}` body, parse `{job_id}` response. Wrap httpx errors in `InspectServiceError` subclasses (mirror `LlmError` pattern from M3).
4. Implement `TrainingClient.stream_progress(job_id: str) -> AsyncIterator[dict]`: opens `/api/training/{job_id}/stream`, yields decoded SSE event dicts.
5. Tests: mock-transport tests for start success, connection refused → `InspectServiceConnectionError`, timeout → `InspectServiceTimeoutError`, malformed JSON → `InspectServiceResponseError`. Plus one SSE test with a `httpx.MockTransport` that returns a multi-event stream — assert iterator yields N dicts.
6. Commit: `feat(inspect): training_client with start + SSE stream + typed errors`

**Verification:**
- [ ] 5 mock-transport tests pass; no live `auto-inspect-service` required
- [ ] Every httpx error wrapped into a typed `InspectServiceError` subclass
- [ ] Async iterator cleans up on cancellation (test asserts no resource leak)
- [ ] No placeholder/TODO

### Phase 7.2: `train_runs` table + migration

**Estimated time:** 8 min

**Files:**
- Create: `alembic/versions/0007_train_runs.py`
- Modify: `src/indusia_visual_editor/db/models.py` (add `TrainRun` model)

**Steps:**
1. Failing test `test_train_run_row_persists`. Expected: `ImportError: cannot import name 'TrainRun'`.
2. Run, see fail.
3. Migration: `train_runs(id UUID PK, project_id UUID FK CASCADE, adapt_run_id UUID FK CASCADE, service_job_id TEXT, status TEXT CHECK in ('pending','running','succeeded','failed','cancelled'), metrics_json JSONB nullable, started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ nullable, error_text TEXT nullable)`. Index (project_id), index (service_job_id).
4. Add `TrainRun` SQLAlchemy model with relationships to Project + AdaptRun (both cascade-delete).
5. Apply migration. Run tests.
6. Commit: `feat(db): train_runs table — service job tracking + metrics`

**Verification:**
- [ ] Alembic downgrade→upgrade clean
- [ ] Status CHECK constraint enforced
- [ ] Cascade-delete from both Project and AdaptRun verified
- [ ] No placeholder/TODO

### Phase 7.3: Training start route + initial row insert

**Estimated time:** 15 min

**Files:**
- Create: `src/indusia_visual_editor/schemas/training.py`
- Create: `src/indusia_visual_editor/routes/training.py`
- Modify: `src/indusia_visual_editor/main.py` (include router + `InspectServiceError` handlers → 502)
- Test: `tests/routes/test_training.py`

**Steps:**
1. Failing test `test_post_training_start_inserts_row_and_calls_service`. Expected: 404.
2. Run, see fail.
3. Implement `POST /api/projects/{id}/training/start`:
   - Lookup latest `AdaptRun` for project; 422 if none.
   - Inject `TrainingClient` factory (test seam mirroring M3 / M4 pattern).
   - Call `start_training(adapt_run.model_dir)` → `job_id`.
   - INSERT `TrainRun` row with `status='pending'`, `service_job_id=job_id`, `started_at=now()`.
   - 201 envelope with row.
4. 4 tests: happy path with fake TrainingClient, 422 no adapt_run, 502 on `InspectServiceConnectionError`, GET (list runs for project).
5. Commit: `feat(training): POST /training/start route + train_runs persistence`

**Verification:**
- [ ] 4 route tests pass
- [ ] 502 envelope on service down; no row leaked
- [ ] Factory seam pattern matches `set_llm_client_factory` (Phase 3.4)
- [ ] No placeholder/TODO

### Phase 7.4: SSE relay endpoint + status updater

**Estimated time:** 15 min

**Files:**
- Modify: `src/indusia_visual_editor/routes/training.py` (add `/stream`)
- Test: `tests/routes/test_training_stream.py`

**Steps:**
1. Failing test `test_get_training_stream_relays_events_and_updates_row`. Expected: 404.
2. Run, see fail.
3. Implement `GET /api/training/{run_id}/stream` returning `sse_starlette.EventSourceResponse`. Inside the generator:
   - Open `TrainingClient.stream_progress(service_job_id)`.
   - For each event: yield it (after wrapping into our envelope's `data` payload). Update `TrainRun.status` if the event signals running/succeeded/failed. Update `metrics_json` on terminal event.
   - On cancellation: best-effort POST `/api/training/{job_id}/cancel` to service (out of scope if service doesn't support it — `try/except`).
4. Test with fake `TrainingClient` yielding a scripted 5-event sequence ending in `succeeded`. Assert SSE response body, assert final `TrainRun.status == 'succeeded'`.
5. Commit: `feat(training): SSE relay /api/training/{id}/stream with row status updates`

**Verification:**
- [ ] Test asserts terminal status persisted
- [ ] Cancellation path doesn't crash if service `/cancel` 404s
- [ ] No placeholder/TODO

---

## M8 — Gate 1 UI (training approval)

### Goal

Before kicking off training, show the operator: dataset stats (region count per defect criterion, MI/SMT split, designator coverage), AI-suggested hyperparameters (epochs, augmentation knobs from Gemma), and a big "Start Training" button. The user MUST click it explicitly — never auto-trigger. The button is the literal gate.

### ADR

**No auto-approval on metric thresholds.** Even if dataset stats look perfect, the operator clicks. CLAUDE.md §11 is explicit.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Dataset stats | `bom_items` + latest `Label` row | new GET endpoint | No | Create new |
| AI hyperparameter suggestion | Gemma 4 call | `services/llm/hyperparams.py` | No | Create new |
| Start training trigger | `POST /training/start` | existing (M7) | Yes | Use existing |
| Gate 1 panel UI | new Vue view | new file | No | Create new |

### Phase 8.1: Dataset stats endpoint

**Estimated time:** 10 min

**Files:**
- Create: `src/indusia_visual_editor/routes/dataset_stats.py`
- Test: `tests/routes/test_dataset_stats.py`

**Steps:**
1. Failing test `test_get_dataset_stats_returns_counts_per_criterion`. Expected: 404.
2. Run, see fail.
3. Implement `GET /api/projects/{id}/dataset/stats?side=top|bottom`:
   - Read `Label` row for side (404 if missing).
   - Parse `ls_json.result[]` via `LSAnnotation` + `derive_inspect_scope`.
   - Tally: total designators, inspected count, skipped count, count per defect criterion, MI-likely vs SMT split (join to `bom_items`).
4. 3 tests: happy path, 404 no label, multi-side independence.
5. Commit.

**Verification:**
- [ ] 3 tests pass
- [ ] Stats reflect REAL `bom_items` joins, not fabricated counts
- [ ] No placeholder/TODO

### Phase 8.2: Hyperparameter suggestion (Gemma call)

**Estimated time:** 12 min

**Files:**
- Create: `src/indusia_visual_editor/services/llm/hyperparams.py`
- Create: `src/indusia_visual_editor/services/llm/prompts/hyperparams.md`
- Test: `tests/services/llm/test_hyperparams.py`

**Steps:**
1. Failing test `test_suggest_hyperparams_returns_validated_schema`. Expected: `ImportError`.
2. Run, see fail.
3. Pydantic schema: `Hyperparameters{epochs: int (5..200), batch_size: int (4..64), augmentation_intensity: Literal['low','medium','high'], notes: str}`.
4. Implement `suggest_hyperparams(client, model, dataset_stats: dict) -> Hyperparameters`. Render `prompts/hyperparams.md`, structured output.
5. 4 mock-transport tests: returns valid, returns out-of-range epochs → `LlmValidationError`, returns invalid intensity → error, no Ollama in test (use fake double).
6. Commit.

**Verification:**
- [ ] 4 mock tests pass
- [ ] Out-of-range values rejected via pydantic
- [ ] Prompt file references CLAUDE.md anti-hallucination guard

### Phase 8.3: Gate 1 panel Vue view

**Estimated time:** 15 min

**Files:**
- Create: `web/src/views/Gate1View.vue`
- Create: `web/src/api/dataset_stats.ts`
- Create: `web/src/api/training.ts` (start training only — stream is M8.4)
- Modify: `web/src/router.ts` (add `/projects/:id/gate1` route)
- Test: `web/src/__tests__/Gate1View.spec.ts`

**Design deliverable:** `gaspol-design` for the stats grid (counts per criterion), hyperparam editor (read-only by default, expandable for advanced override), big primary "Mulai Training" button with disabled-state on missing labels.

**Steps:**
1. Failing Vitest spec mounting Gate1View with mocked stats endpoint. Expected: `Cannot find name 'Gate1View'`.
2. Run, see fail.
3. Implement view: fetch stats on mount, render counts, render Gemma suggestions, show button. On click → POST `/training/start` → router push to streaming view.
4. 3+ Vitest tests: render with stats, disable button when no labels, button click triggers API.
5. Commit.

**Verification:**
- [ ] 3+ Vitest tests pass
- [ ] Button disabled when stats endpoint 404s (no labels yet)
- [ ] Bahasa Indonesia throughout
- [ ] No `console.log` outside DEV

### Phase 8.4: Live training progress view (consumes SSE)

**Estimated time:** 12 min

**Files:**
- Create: `web/src/views/TrainingProgressView.vue`
- Modify: `web/src/api/training.ts` (add `streamProgress(runId, onEvent)` using `EventSource`)
- Test: `web/src/__tests__/TrainingProgressView.spec.ts`

**Steps:**
1. Failing Vitest spec mounting view with mocked `EventSource`. Expected: `Cannot find name 'TrainingProgressView'`.
2. Run, see fail.
3. Implement view: opens EventSource on mount, shows progress bar, current epoch, loss/mAP line chart (Chart.js or vanilla SVG), terminal state badge.
4. On `succeeded` event → router push to `/projects/:id/eval/:runId` (M9).
5. 3 tests: progressive events update DOM, terminal `failed` shows envelope, cancel-button closes stream.
6. Commit.

**Verification:**
- [ ] 3+ tests pass
- [ ] EventSource cleaned up on unmount
- [ ] Final state navigates correctly
- [ ] No placeholder/TODO

---

## M9 — Eval view

### Goal

After training succeeds, present the metrics that decide whether the model goes to production. Per-component F1 (not just global mAP — single-class F1 hides regressions), confusion matrix, sample predictions grid (10 worst false-positives + 10 worst false-negatives), and comparison vs the previous successful run.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Metrics JSON | `train_runs.metrics_json` | SQLAlchemy `select` | Yes (after M7) | Use existing |
| Sample predictions | `auto-inspect-service /api/eval/{run_id}/predictions` | new client method | No | Extend `inspect_service` client |
| Previous run comparison | second-most-recent succeeded `TrainRun` | SQLAlchemy | Yes | Use existing |
| Chart components | Chart.js or vanilla SVG | new Vue components | No | Create new |

### Phase 9.1: Predictions fetch + endpoint

**Estimated time:** 12 min

**Files:**
- Modify: `services/inspect_service/training_client.py` (add `get_predictions`)
- Create: `routes/eval.py`
- Test: `tests/routes/test_eval.py`

**Steps:**
1. Failing test `test_get_eval_returns_metrics_and_predictions`. Expected: 404.
2. Run, see fail.
3. Add `TrainingClient.get_predictions(job_id) -> list[dict]` — GET sibling endpoint.
4. Implement `GET /api/training/{run_id}/eval`: load TrainRun, fetch sample predictions, return combined `{metrics, predictions, prev_metrics}`.
5. 3 tests: happy path, 404 missing run, 422 if run not succeeded yet.
6. Commit.

**Verification:**
- [ ] 3 tests pass
- [ ] No placeholder/TODO

### Phase 9.2: Eval Vue view

**Estimated time:** 18 min

**Files:**
- Create: `web/src/views/EvalView.vue`
- Create: `web/src/components/MetricChart.vue`
- Create: `web/src/components/PredictionGrid.vue`
- Create: `web/src/api/eval.ts`
- Test: `web/src/__tests__/EvalView.spec.ts`

**Design deliverable:** `gaspol-design` for metric chart styling (line for mAP curve, bar for per-component F1), prediction grid (10 worst FP + 10 worst FN, hover reveals annotation overlay), and comparison delta indicators (▲ +0.03 mAP in green, ▼ -0.01 in amber).

**Steps:**
1. Failing Vitest mounting EvalView. Expected: `Cannot find name 'EvalView'`.
2. Run, see fail.
3. Implement view + 2 components. Fetch via `eval.ts` on mount.
4. 4+ Vitest tests: render charts, render grid, render comparison delta, handle missing prev_metrics gracefully.
5. Commit.

**Verification:**
- [ ] 4+ tests pass
- [ ] Per-component F1 visualized (not just global mAP)
- [ ] Bahasa Indonesia
- [ ] No `console.log` outside DEV

---

## M10 — Gate 2 + promote-to-production

### Goal

Operator reviews eval metrics, decides to ship. Backend invokes `ais model push` (subprocess) to push weights to the Git+LFS registry. The model is then loadable by edges. New `deployments` table records the promotion event.

### ADR

**Subprocess to `ais model push`, NOT REST.** `auto-inspect-service` doesn't expose a REST endpoint for the model registry — the only interface is the `ais` CLI which uses git+LFS internally. Subprocess gives us atomic push behavior with stderr capture; lifecycle is short (<1 min) so process management is straightforward.

### Phase 10.1: Spike — verify `ais model push` interface

**Estimated time:** 15 min

**Files:**
- Create: `docs/specs/ais-model-push.md`

**Steps:**
1. Failing test `test_ais_cli_is_installed_and_responsive` (smoke check). Expected: `FileNotFoundError`.
2. Run, see fail (or pass if already installed).
3. Document in `docs/specs/ais-model-push.md`:
   - exact command shape (`ais model push <name> --version <semver>`)
   - working dir requirements (must be inside model registry repo?)
   - auth requirements (Git credentials or LFS token)
   - stdout/stderr format (parse for success/failure markers)
   - timing: typical duration
4. If `ais` not installed locally, document the install procedure and skip the smoke test.
5. Commit.

**Verification:**
- [ ] Document covers command shape, auth, working dir, output format
- [ ] Smoke test passes or skipif with reason

### Phase 10.2: `deployments` table + migration

**Estimated time:** 8 min

**Files:**
- Create: `alembic/versions/0008_deployments.py`
- Modify: `src/indusia_visual_editor/db/models.py` (add `Deployment` model)

**Steps:**
1. Failing test `test_deployment_row_persists`. Expected: `ImportError`.
2. Migration: `deployments(id UUID PK, project_id UUID FK CASCADE, train_run_id UUID FK CASCADE, model_version TEXT, edges_notified JSONB nullable, status TEXT CHECK in ('pending','succeeded','failed'), deployed_at TIMESTAMPTZ default now(), error_text TEXT nullable)`. Index (project_id).
3. Add `Deployment` SQLAlchemy model. Apply migration.
4. Commit.

**Verification:**
- [ ] Migration downgrade/upgrade clean
- [ ] Cascade-deletes from Project + TrainRun verified
- [ ] No placeholder/TODO

### Phase 10.3: Promote route + subprocess wrapper

**Estimated time:** 18 min

**Files:**
- Create: `src/indusia_visual_editor/services/deploy/__init__.py`
- Create: `src/indusia_visual_editor/services/deploy/registry.py`
- Create: `src/indusia_visual_editor/routes/deploy.py`
- Test: `tests/services/deploy/test_registry.py`, `tests/routes/test_deploy.py`

**Steps:**
1. Failing service-test `test_push_model_runs_ais_cli_subprocess`. Expected: `ImportError`.
2. Run, see fail.
3. Implement `services/deploy/registry.py::push_model(model_name, version) -> PushResult`: `asyncio.create_subprocess_exec('ais', 'model', 'push', model_name, '--version', version)`. Capture stdout/stderr. Return `{ok: bool, output: str, error: str | None}`.
4. Failing route-test `test_post_promote_inserts_deployment_row`. Expected: 404.
5. Implement `POST /api/projects/{id}/deploy`: lookup latest succeeded `TrainRun`, derive `model_name` from project slug + `version` from run timestamp, call `push_model`, INSERT `Deployment` row with status reflecting subprocess result, return 201.
6. 5 tests total (3 service + 2 route): happy path with mocked subprocess, subprocess non-zero exit → status='failed' + 502, 422 no succeeded train_run, 404 missing project, GET deploy history.
7. Commit.

**Verification:**
- [ ] All 5 tests pass with mocked `asyncio.create_subprocess_exec`
- [ ] Failed subprocess → status='failed', row persisted, 502 envelope
- [ ] Real `ais` invocation gated behind `IVE_AIS_INTEGRATION` env (skipif unset)
- [ ] No placeholder/TODO

### Phase 10.4: Gate 2 Vue view + Promote button

**Estimated time:** 12 min

**Files:**
- Create: `web/src/views/Gate2View.vue`
- Create: `web/src/api/deploy.ts`
- Modify: `web/src/router.ts`
- Test: `web/src/__tests__/Gate2View.spec.ts`

**Design deliverable:** `gaspol-design` for the eval summary card (mAP + F1 numbers), comparison vs previous deployment, big red "Promote to Production" button with confirmation modal.

**Steps:**
1. Failing Vitest mount test. Expected: `Cannot find name 'Gate2View'`.
2. Run, see fail.
3. Implement view: reads latest TrainRun + previous Deployment, shows side-by-side, confirmation modal on click, POST `/deploy`, navigates to deployment status view.
4. 3 tests: render, button click opens confirmation, confirm triggers API.
5. Commit.

**Verification:**
- [ ] 3 tests pass
- [ ] Confirmation modal prevents accidental promotions
- [ ] Bahasa Indonesia
- [ ] No placeholder/TODO

---

## M11 — Edge notification + version pin

### Goal

Each edge node registers itself once with the visual-editor (so visual-editor knows where to send refresh webhooks). On a successful M10 promotion, send a POST to every registered edge's `/api/models/refresh-cache`. Per-edge policy: `auto_pull_latest` vs `pinned_version=<semver>`. Edges receiving the webhook decide whether to pull based on their policy. Manual rollback route lets the operator pin an older version.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Edge registry | new `edges` table | new model + migration | No | Create new |
| Webhook target | `edges.webhook_url` | direct httpx POST | No | New `services/edge/notify.py` |
| Refresh trigger | M10 Deployment row hook | new route + service call | No | Wire into M10 flow |
| Version pin policy | `edges.version_policy` JSONB | direct read | No | New column in edges table |

### Phase 11.1: `edges` table + registration route

**Estimated time:** 12 min

**Files:**
- Create: `alembic/versions/0009_edges.py`
- Modify: `src/indusia_visual_editor/db/models.py`
- Create: `src/indusia_visual_editor/routes/edges.py`
- Test: `tests/routes/test_edges.py`

**Steps:**
1. Failing test `test_register_edge_persists_row`. Expected: 404.
2. Run, see fail.
3. Migration: `edges(id UUID PK, name TEXT UNIQUE, webhook_url TEXT, version_policy JSONB DEFAULT '{"mode":"auto_pull_latest"}', registered_at TIMESTAMPTZ default now(), last_seen_at TIMESTAMPTZ nullable)`.
4. POST `/api/edges` body `{name, webhook_url, version_policy}` → 201. GET `/api/edges` list. PUT `/api/edges/{id}` for policy updates.
5. 4 tests: register, duplicate name → 409, list, update policy.
6. Commit.

**Verification:**
- [ ] 4 tests pass
- [ ] Unique constraint on name enforced
- [ ] No placeholder/TODO

### Phase 11.2: Notify-on-deploy webhook with retry

**Estimated time:** 15 min

**Files:**
- Create: `src/indusia_visual_editor/services/edge/__init__.py`
- Create: `src/indusia_visual_editor/services/edge/notify.py`
- Modify: `src/indusia_visual_editor/routes/deploy.py` (call notify after successful push)
- Test: `tests/services/edge/test_notify.py`

**Steps:**
1. Failing test `test_notify_edges_sends_webhook_with_retry`. Expected: `ImportError`.
2. Run, see fail.
3. Implement `notify_edges(deployment: Deployment, session) -> NotifyResult`: load all edges, decide per-edge whether to notify based on `version_policy.mode`, POST `{model_name, version}` to `webhook_url`. Exponential backoff retry: 3 attempts with 1/2/4s spacing.
4. Update Deployment row's `edges_notified` JSONB with per-edge `{name, status, attempts}`.
5. Call from M10 promote handler after successful push.
6. 4 mock-transport tests: notify success, notify with retry-then-success, notify exhaust retries, pinned edge skipped.
7. Commit.

**Verification:**
- [ ] 4 tests pass
- [ ] `edges_notified` JSONB reflects final state
- [ ] No placeholder/TODO

### Phase 11.3: Manual rollback route

**Estimated time:** 10 min

**Files:**
- Modify: `src/indusia_visual_editor/routes/edges.py` (add `PUT /api/edges/{id}/pin`)
- Test: `tests/routes/test_edges.py` (extend)

**Steps:**
1. Failing test `test_pin_edge_updates_policy`. Expected: 404.
2. Run, see fail.
3. Implement endpoint: body `{model_name, version}` → updates `edges.version_policy = {mode: 'pinned', model_name, version}`. Triggers a webhook to the edge with the pinned target.
4. 2 tests: pin happy path, unpin (set back to `auto_pull_latest`).
5. Commit.

**Verification:**
- [ ] 2 tests pass
- [ ] Webhook fired on pin change
- [ ] No placeholder/TODO

---

## M12 — Chat advisor

### Goal

Slide-out drawer in the UI. Operator types "C4 false-positive 5% di line 3, kenapa?" — Gemma sees project metadata + last 20 chat turns + the 3 most recent ROI crops with elevated false-positive rate + latest train_runs metrics, and answers in Bahasa Indonesia with concrete next steps (retrain with new examples, tweak threshold, etc).

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Chat history | new `chat_sessions` table | new model + migration | No | Create new |
| Project context | Project + TrainRun + recent deployments | SQLAlchemy joins | Yes | Use existing |
| ROI crops | inference results in `auto-inspect-service` | new client method | No | Extend `inspect_service` client |
| Streaming SSE | sse-starlette | existing pattern (M7) | Yes (pattern) | Reuse |
| Vue chat drawer | new component | new file | No | Create new |

### Phase 12.1: `chat_sessions` table + history APIs

**Estimated time:** 10 min

**Files:**
- Create: `alembic/versions/0010_chat_sessions.py`
- Modify: `src/indusia_visual_editor/db/models.py`
- Create: `src/indusia_visual_editor/routes/chat.py`

**Steps:**
1. Failing test `test_chat_session_row_persists`. Expected: `ImportError`.
2. Migration: `chat_sessions(id UUID PK, project_id UUID FK CASCADE, messages_json JSONB DEFAULT '[]', created_at TIMESTAMPTZ default now(), updated_at TIMESTAMPTZ)`.
3. Add `ChatSession` model.
4. Implement `GET /api/projects/{id}/chat` → list sessions, `POST /api/projects/{id}/chat` → create new session, `GET /api/chat/{session_id}` → full message list.
5. 4 tests.
6. Commit.

**Verification:**
- [ ] 4 tests pass
- [ ] No placeholder/TODO

### Phase 12.2: Chat context builder

**Estimated time:** 15 min

**Files:**
- Create: `src/indusia_visual_editor/services/llm/chat.py`
- Create: `src/indusia_visual_editor/services/llm/prompts/advisor.md`
- Test: `tests/services/llm/test_chat.py`

**Steps:**
1. Failing test `test_build_chat_context_includes_recent_metrics_and_turns`. Expected: `ImportError`.
2. Run, see fail.
3. Implement `build_chat_context(session: AsyncSession, project_id, session_id, user_message) -> ChatRequest`: pulls last 20 turns + last 3 train_runs metrics + project metadata; truncates aggressively at 200K tokens.
4. Author `prompts/advisor.md` system prompt — Bahasa Indonesia tone, concrete next-step format.
5. 3 tests: 20-turn truncation, metric injection, token-cap enforcement.
6. Commit.

**Verification:**
- [ ] 3 tests pass
- [ ] Token cap respected (test asserts string length under bound)
- [ ] No placeholder/TODO

### Phase 12.3: Streaming chat SSE endpoint

**Estimated time:** 15 min

**Files:**
- Modify: `src/indusia_visual_editor/routes/chat.py` (add `/stream`)
- Modify: `src/indusia_visual_editor/services/llm/client.py` (add `stream_chat` method)
- Test: `tests/routes/test_chat_stream.py`

**Steps:**
1. Failing test `test_chat_stream_emits_chunks_and_persists_terminal`. Expected: 404.
2. Run, see fail.
3. Add `OllamaClient.stream_chat(model, messages) -> AsyncIterator[str]` — opens `/api/chat` with `stream=true`, yields chunks.
4. Implement `POST /api/chat/{session_id}/stream` body `{user_message}`: appends user turn, builds context, calls `stream_chat`, relays chunks via sse-starlette, on completion appends assistant turn to `chat_sessions.messages_json` + 200.
5. 3 tests with fake-iterator client double.
6. Commit.

**Verification:**
- [ ] 3 tests pass
- [ ] Terminal persistence verified
- [ ] No placeholder/TODO

### Phase 12.4: Vue chat drawer

**Estimated time:** 15 min

**Files:**
- Create: `web/src/components/ChatDrawer.vue`
- Create: `web/src/stores/chat.ts`
- Create: `web/src/api/chat.ts`
- Modify: `web/src/views/Dashboard.vue` or layout shell to mount drawer
- Test: `web/src/__tests__/ChatDrawer.spec.ts`

**Design deliverable:** `gaspol-design` for slide-out animation, message bubble styling (user right, assistant left), code-block + image embed rendering, typing indicator while streaming.

**Steps:**
1. Failing Vitest mount test. Expected: `Cannot find name 'ChatDrawer'`.
2. Run, see fail.
3. Implement: floating button bottom-right, click opens drawer, message list, input + send, EventSource for streaming response.
4. 4 Vitest tests.
5. Commit.

**Verification:**
- [ ] 4 tests pass
- [ ] Drawer animation smooth (no jank in manual smoke)
- [ ] Bahasa Indonesia copy
- [ ] No `console.log` outside DEV

---

## M13 — Auth + multi-user

### Goal

JWT bearer auth with bcrypt password hashing. User + Organization tables. Project ownership filter (queries scoped to user's org). Three roles: `admin` (CRUD users + projects), `engineer` (CRUD own projects, train + deploy), `viewer` (read-only).

### Phase 13.1: User + organization schema + bcrypt hashing

**Estimated time:** 12 min

**Files:**
- Create: `alembic/versions/0011_auth.py`
- Modify: `src/indusia_visual_editor/db/models.py` (add `User`, `Organization`, add `organization_id` to `Project`)
- Create: `src/indusia_visual_editor/services/auth/passwords.py`
- Test: `tests/services/auth/test_passwords.py`

**Steps:**
1. Failing test `test_hash_and_verify_password_roundtrip`. Expected: `ImportError`.
2. Migration: `organizations(id UUID PK, name TEXT, slug TEXT UNIQUE, created_at)`. `users(id UUID PK, organization_id UUID FK, email TEXT UNIQUE, password_hash TEXT, role TEXT CHECK in ('admin','engineer','viewer'), created_at)`. Add `organization_id` to `projects` (nullable initially; backfill in same migration to seed-org).
3. Add `User`, `Organization` SQLAlchemy models. Extend `Project` with relationship.
4. Implement `services/auth/passwords.py::hash_password` + `verify_password` using `passlib.context.CryptContext(['bcrypt'])`.
5. 3 tests: hash deterministic-unequal (salt), verify roundtrip, verify wrong password rejects.
6. Commit.

**Verification:**
- [ ] 3 tests pass
- [ ] No plaintext passwords anywhere in code or logs
- [ ] No placeholder/TODO

### Phase 13.2: JWT token service + login endpoint

**Estimated time:** 15 min

**Files:**
- Create: `src/indusia_visual_editor/services/auth/jwt_service.py`
- Create: `src/indusia_visual_editor/routes/auth.py`
- Modify: `src/indusia_visual_editor/config.py` (add `auth_jwt_secret: str` + `auth_jwt_ttl_seconds: int = 3600`)
- Test: `tests/services/auth/test_jwt.py`, `tests/routes/test_auth.py`

**Steps:**
1. Failing service-test `test_create_and_verify_jwt`. Expected: `ImportError`.
2. Implement `jwt_service.create_token(user_id, role) -> str` + `verify_token(token) -> TokenPayload` via `python-jose` HS256.
3. Implement `POST /api/auth/login` body `{email, password}` → verify against `users` table → return `{access_token, refresh_token, user: {...}}`. Refresh token in HttpOnly cookie.
4. Implement `POST /api/auth/refresh` reading cookie → new access token.
5. 5 tests: login happy, login wrong password → 401 envelope, login unknown email → 401, refresh happy, refresh missing cookie → 401.
6. Commit.

**Verification:**
- [ ] 5 tests pass
- [ ] No plaintext password in test fixtures (use `hash_password` in seed)
- [ ] JWT secret comes from env (test sets `IVE_AUTH_JWT_SECRET=test-secret`)
- [ ] No placeholder/TODO

### Phase 13.3: Auth middleware + protected routes

**Estimated time:** 12 min

**Files:**
- Create: `src/indusia_visual_editor/services/auth/dependencies.py` (FastAPI `Depends`)
- Modify: `src/indusia_visual_editor/routes/*.py` (add `current_user` dep to mutation endpoints)
- Test: `tests/routes/test_auth_middleware.py`

**Steps:**
1. Failing test `test_post_projects_without_token_returns_401`. Expected: 200 (since route currently unprotected).
2. Run, see fail.
3. Implement `Depends(get_current_user)` reading `Authorization: Bearer <token>` header.
4. Add the dep to all POST/PUT/DELETE routes in existing modules.
5. 4 tests: missing token → 401, valid token → 200, expired token → 401, malformed token → 401.
6. Commit.

**Verification:**
- [ ] 4 tests pass
- [ ] All mutation endpoints protected (test confirms 401 without token for each module's POST)
- [ ] GET endpoints stay open for v1 (read-only viewer role uses GETs without auth) OR also protected — DECISION POINT, lock in here
- [ ] No placeholder/TODO

### Phase 13.4: RBAC + project-scope filter

**Estimated time:** 12 min

**Files:**
- Create: `src/indusia_visual_editor/services/auth/rbac.py`
- Modify: `src/indusia_visual_editor/services/project/crud.py` (filter by `organization_id`)
- Modify: `src/indusia_visual_editor/routes/projects.py` (admin-only DELETE etc)
- Test: `tests/services/auth/test_rbac.py`

**Steps:**
1. Failing test `test_engineer_cannot_delete_others_project`. Expected: 200.
2. Run, see fail.
3. Implement `Depends(require_role('admin'))` + `Depends(require_role('engineer'))` factories.
4. Update CRUD: `list_projects(session, organization_id)` filters by org; `delete_project` requires admin role.
5. 5 tests: viewer cannot create, engineer can create + train, engineer cannot delete others, admin can do everything, cross-org isolation.
6. Commit.

**Verification:**
- [ ] 5 tests pass
- [ ] Engineer of org A cannot access project of org B (cross-org isolation test)
- [ ] No placeholder/TODO

### Phase 13.5: Vue login + signup + session management

**Estimated time:** 18 min

**Files:**
- Create: `web/src/views/LoginView.vue`
- Create: `web/src/views/SignupView.vue`
- Create: `web/src/stores/auth.ts`
- Create: `web/src/api/auth.ts`
- Modify: `web/src/api/client.ts` (interceptor adds bearer token + handles 401 → refresh + retry)
- Modify: `web/src/router.ts` (add route guards: redirect to `/login` if no token)
- Test: `web/src/__tests__/LoginView.spec.ts`, `web/src/__tests__/auth.spec.ts`

**Design deliverable:** `gaspol-design` for login + signup forms (Bahasa Indonesia copy, email + password inputs, error envelope display, "Lupa password?" link out of scope for v1), session indicator in navbar.

**Steps:**
1. Failing Vitest. Expected: missing components.
2. Run, see fail.
3. Implement auth store (token in localStorage, refresh in HttpOnly cookie handled by browser), client interceptor (Bearer header on every request, 401 → refresh + retry), router guard.
4. Implement Login + Signup views.
5. 4+ Vitest tests.
6. Commit.

**Verification:**
- [ ] 4+ tests pass
- [ ] Logged-out user redirected from protected routes
- [ ] Logged-in user persists across page reload
- [ ] No `console.log` outside DEV
- [ ] No placeholder/TODO

---

## M14 — Polish + production deploy

### Goal

Production-grade Docker images (multi-stage builds, non-root user, slim base images), Traefik reverse proxy with auto-Let's-Encrypt, Postgres backup automation, structured logging migration, OpenTelemetry-ready spans on outbound LLM/service calls, and a deployment runbook.

### Phase 14.1: Production Dockerfiles (backend + frontend)

**Estimated time:** 18 min

**Files:**
- Create: `Dockerfile.api` (multi-stage; current dev one is single-stage)
- Create: `web/Dockerfile` (production — currently dev-only)
- Modify: `.dockerignore` (ensure no leakage)
- Test: `tests/spike/test_docker_build.sh` (CI smoke — builds both images, asserts size < 800MB backend / < 100MB frontend nginx)

**Steps:**
1. Failing test: build both images, assert size limits. Expected: image size or build failure.
2. Run, see fail (likely current images too large or won't build cleanly).
3. Backend `Dockerfile.api`: stage 1 builder (`python:3.10-slim` + poetry install), stage 2 runtime (`python:3.10-slim` + non-root user + only `/.venv` copied + uvicorn entrypoint).
4. Frontend `web/Dockerfile`: stage 1 builder (`node:24-alpine` + `corepack pnpm install` + `pnpm build`), stage 2 runtime (`nginx:alpine` + custom config serving `/dist`).
5. Update `.dockerignore` to exclude `tests/`, `.git/`, `docs/`, dev-only files.
6. Build both. Verify image sizes.
7. Commit.

**Verification:**
- [ ] Backend image < 800MB
- [ ] Frontend image < 100MB
- [ ] Non-root user verified (`docker inspect`)
- [ ] No source code in frontend runtime layer (only built artifacts)
- [ ] No placeholder/TODO

### Phase 14.2: Traefik configuration

**Estimated time:** 12 min

**Files:**
- Create: `infra/traefik/traefik.yml` (static config)
- Create: `infra/traefik/dynamic.yml` (dynamic routing rules)
- Create: `docker-compose.prod.yml`
- Modify: `Dockerfile.api`, `web/Dockerfile` (add Traefik labels)
- Test: `tests/spike/test_traefik_config.py` (validates YAML schema)

**Steps:**
1. Failing test: parse Traefik YAML, assert required entries exist. Expected: file not found.
2. Run, see fail.
3. Author Traefik static + dynamic configs: HTTP→HTTPS redirect, Let's Encrypt ACME challenge with `httpchallenge`, separate routers for `api.<domain>` → backend service + `<domain>` → frontend service.
4. Author `docker-compose.prod.yml` with Traefik service + backend + frontend + postgres (named volume) + ollama (optional external).
5. Test validates YAML parses + checks routes/services/middlewares exist.
6. Commit.

**Verification:**
- [ ] Traefik config validates against schema
- [ ] HTTPS redirect rule present
- [ ] ACME challenge configured
- [ ] No placeholder/TODO

### Phase 14.3: Postgres backup automation

**Estimated time:** 12 min

**Files:**
- Create: `infra/scripts/pg_backup.sh`
- Create: `infra/scripts/pg_restore.sh`
- Modify: `docker-compose.prod.yml` (add cron container or ofelia scheduler)
- Test: `tests/spike/test_pg_backup.sh` (runs backup + restore in throwaway containers)

**Steps:**
1. Failing test that runs both scripts end-to-end against a throwaway Postgres. Expected: missing script files.
2. Run, see fail.
3. Implement `pg_backup.sh`: `pg_dump -Fc` to timestamped file, upload to S3-compatible storage via `aws s3 cp` (configurable endpoint).
4. Implement `pg_restore.sh`: pull from S3, `pg_restore -d` into target.
5. Schedule daily via ofelia or cron container in prod compose.
6. Test the roundtrip.
7. Commit.

**Verification:**
- [ ] Backup → restore roundtrip preserves data
- [ ] Daily schedule documented
- [ ] No plaintext credentials in scripts (env vars)
- [ ] No placeholder/TODO

### Phase 14.4: Structured logging migration

**Estimated time:** 15 min

**Files:**
- Modify: `pyproject.toml` (add `structlog`)
- Create: `src/indusia_visual_editor/utils/logging_config.py`
- Modify: `src/indusia_visual_editor/main.py` (replace stdlib `logging.basicConfig` with structlog wiring)
- Modify: all modules using `logger.info(...)` with `extra={...}` to use structlog context
- Test: `tests/utils/test_logging.py`

**Steps:**
1. Failing test `test_logger_emits_json_with_correlation_fields`. Expected: `ImportError` or `AssertionError`.
2. Run, see fail.
3. Configure structlog: JSON renderer in prod, console renderer in dev (via env var). Bind `project_id`, `train_run_id`, `deployment_id`, `request_id` (UUID per request via middleware) as context vars.
4. Update existing call sites to use `structlog.get_logger(__name__)` and `logger.info(...)` with kwargs not `extra=`.
5. Add middleware that binds `request_id` per request.
6. Test asserts JSON output shape contains correlation fields.
7. Commit.

**Verification:**
- [ ] All `logger.info` calls migrated
- [ ] JSON output in prod env, console in dev
- [ ] `request_id` correlation works across nested calls
- [ ] No placeholder/TODO

### Phase 14.5: OpenTelemetry spans on outbound calls

**Estimated time:** 12 min

**Files:**
- Modify: `pyproject.toml` (add `opentelemetry-api` + `opentelemetry-instrumentation-httpx`)
- Modify: `src/indusia_visual_editor/services/llm/client.py` (add span around generate/chat)
- Modify: `src/indusia_visual_editor/services/inspect_service/training_client.py` (add span)
- Test: `tests/utils/test_otel_spans.py`

**Steps:**
1. Failing test that captures spans via `InMemorySpanExporter` and asserts spans exist for Ollama and inspect_service calls. Expected: no spans captured.
2. Run, see fail.
3. Add `tracer = trace.get_tracer(__name__)` and `with tracer.start_as_current_span("llm.generate")` wrapping each outbound call. Attribute: model name, byte size, status.
4. Test asserts span names + attributes.
5. NB: do NOT wire a collector in v1 — spans go to no-op exporter by default. Future M15+ wires Jaeger/Tempo.
6. Commit.

**Verification:**
- [ ] Spans recorded for `OllamaClient.generate`, `OllamaClient.chat`, `TrainingClient.start_training`, `TrainingClient.stream_progress`
- [ ] Attribute names follow OpenTelemetry semantic conventions
- [ ] No collector required in v1
- [ ] No placeholder/TODO

### Phase 14.6: Deployment runbook

**Estimated time:** 18 min

**Files:**
- Create: `docs/runbooks/deploy.md`
- Create: `docs/runbooks/disaster-recovery.md`
- Create: `docs/runbooks/onboarding.md`

**Steps:**
1. No failing test for docs — but lock in a smoke check: `tests/spike/test_runbook_links.py` that asserts every internal link in the runbooks resolves to a real file. Expected: missing files.
2. Run, see fail.
3. Write `deploy.md`: step-by-step from fresh VPS to running service (Traefik DNS, ACME bootstrap, env file, docker compose up, smoke `/health`).
4. Write `disaster-recovery.md`: Postgres restore procedure, edge re-registration, model registry restore from Git+LFS clone.
5. Write `onboarding.md`: developer first-day setup (poetry, pnpm, docker compose dev, run tests).
6. Test passes.
7. Commit.

**Verification:**
- [ ] All internal links resolve (test enforces this)
- [ ] Runbooks cover: fresh deploy, DR restore, dev onboarding
- [ ] No placeholder/TODO

---

## Cross-milestone test counts (target end of M14)

| Milestone | New tests | Cumulative |
|---|---|---|
| Baseline (M4 close) | 158 | 158 |
| M5 | ~20 | ~178 |
| M6 | ~25 | ~203 |
| M7 | ~15 | ~218 |
| M8 | ~15 | ~233 |
| M9 | ~10 | ~243 |
| M10 | ~12 | ~255 |
| M11 | ~12 | ~267 |
| M12 | ~14 | ~281 |
| M13 | ~25 | ~306 |
| M14 | ~15 | ~321 |

## Execution Handoff

| Option | Action |
|---|---|
| **Sequential** | `gaspol-execute` on this file starting at M5 Phase 5.1. Per-phase checkpoint approval. |
| **Parallel (within milestone)** | `gaspol-parallel` mode `plan-phases` — many milestones have 3–4 phases where 2 are independent (e.g. M11 Phase 11.1 + 11.3 can run parallel, M5 Phase 5.1 + 5.2 are independent). |
| **Separate session** | Restart with `/gaspol-execute docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md` and point at a specific milestone. |

## Out-of-scope (explicit non-goals for M5–M14)

- OAuth login flows (M13 is email/password only; OAuth = v1.5)
- Model registry UI (M10 uses CLI subprocess; a Vue model browser is v1.5)
- Multi-camera per edge (M11 assumes one camera per edge node)
- Active learning loop (chat suggestions don't auto-retrain; user does it manually)
- A/B testing of two model versions on one line (single deployed version per project per edge)
- Custom defect taxonomy per project (the 9 canonical defects are fixed; project-specific defect types = v1.5)
- LSF ML Backend protocol (deferred from M6 to v1.5 per ADR)

---

*This breakdown is the executable spec for M5 through M14. M0–M4 detail lives in the companion file [2026-05-22-visual-editor-mvp.md](./2026-05-22-visual-editor-mvp.md).*
