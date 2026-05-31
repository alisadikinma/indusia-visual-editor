# T1 — `defect_examples` → trainer ingest contract (design + TDD plan)

> **Status:** design proposal — NO production code written yet. Awaiting operator approval before implementation.
> **Date:** 2026-05-31
> **Scope:** cross-repo — `indusia-visual-editor` (sender) + `auto-inspect-service` (receiver/trainer). Both now owned by PT Indusia (alisadikinma), so the foreign-repo blocker that deferred T1 is gone (see memory `sibling-repos-migrated`).
> **Inspection-domain gate:** validated against `ai-visual-inspection-expert` skill + its reference files (CLAUDE.md §16.16). Routing below is grounded, not improvised.

---

## 1. Goal

Close the inspection-feedback loop's last open half: make **promoted `defect_examples`** (operator-confirmed production escapes — an ROI crop + one defect criterion) actually **reach and improve the next supervised retrain**, instead of accumulating in our DB unconsumed.

Today (verified in code, 2026-05-31):
- Our side stops at the DB. `defect_examples` rows exist (migration `0012`), but our `training/start` sends only `{"model_dir": ...}` (config-only; the `assets/` dir we write is empty). There is no LS→YOLO / crop exporter on our side.
- **The service side is richer than the earlier T1 finding assumed.** `auto-inspect-service` v0.6.0 already has a full dataset-ingestion + training API. T1 is therefore *not* "build an exporter from zero" — it is "push our crops into the layout the trainer already consumes, routed to the right detector track per criterion."

---

## 2. What `auto-inspect-service` ALREADY provides (the discovered contract)

Read from `services/setup_dataset.py`, `services/training_service.py`, `routes/api/setup.py`, `routes/api/training.py`, `cli/commands/train.py`.

### 2.1 Dataset layout the trainer consumes
```
storage/dataset/{model_name}/{component}/{label}/*.png      # preferred (storage-based)
{model_dir}/dataset/{component}/{label}/*.png               # legacy fallback
```
- `label ∈ {good, ng, train, test}`. Resolution helper: `_resolve_dataset_dir()` (storage first, then model_dir; handles single-nesting).
- **Anomaly track** (`_train_single_component` → `prepare_anomaly_dataset`): trains on `{component}/good/` only (one-class). MVTec split into `train/good`, `test/good`. **`ng/` crops are the eval/test set** — they drive TP/TN/FP/FN + threshold, they do NOT train the anomaly model.
- **YOLO detect/obb** (`run_train_yolo`): consumes `data_path/images/` + `data_path/labels/` (standard YOLO).
- **YOLO classify**: consumes `data_path/train/{class_name}/`.

### 2.2 Ingest endpoints that already exist
| Endpoint | What it does | Reuse for T1? |
|---|---|---|
| `POST /setup/{model}/crop` (multipart `image`+`frame_id`) | crops a full frame into per-component ROIs via `components_manifest.yaml`, saves each as **good** | Pattern to mirror; hard-codes `good/` so not directly reusable for defects |
| `POST /setup/{model}/dataset/{component}/images/{filename}/move` (`target_label`) | moves an image good↔ng | The "mark as defect" primitive already exists |
| `POST /setup/{model}/yolo/prepare` / `/yolo/detect` / `/yolo/augment` / `/yolo/filter` | full YOLO data-prep incl. **synthetic augmentation** | Augmentation track for supervised defects |
| `POST /setup/{model}/import-labelstudio` | imports an LS export → manifest + fiducial crops | Precedent for an LS-shaped bulk import |
| `POST /training/jobs` (`model_name, components, algorithm, overrides, data_dir`) | starts a job; SSE at `/training/jobs/{id}/events` | The training trigger we already call |

### 2.3 Synthetic defect generator (engine)
`auto_inspect_engine.utils.synthetic_damage.generate_synthetic_dataset(component_dir, defect_classes, max_per_class)` + `DEFAULT_DEFECT_CLASSES`, wired through `_train_single_component(generate_synthetic=…, defect_classes=…)` and the `--generate-synthetic` CLI flag. So the "400 real + 1000 synthetic" recipe is already executable service-side.

**Consequence:** the missing piece is a thin **defect-crop ingest** that writes our `defect_examples` into `{component}/ng/` (anomaly track) and/or the YOLO `images/+labels/` set (supervised track), with the class routed per criterion. Everything downstream already runs.

---

## 3. Inspection-expert validation — routing per criterion

Grounded in `references/model-defect-matrix.csv` + `model-selection-per-defect.md` §2–4 + our existing `data/defect_detector_mapping.yaml` (which already encodes detector presets per criterion).

**Q1 — supervised YOLO vs anomaly `ng/`, or both?** → **Both, different roles.** A confirmed escape is a *known, labeled, repeating* defect → primary home is the **supervised** track (it learns to localize+classify). It is *also* appended to the matching component's **anomaly `ng/`** set, because anomaly trains good-only and uses `ng/` to tighten its threshold — so the same escape is caught next run as a regression test, even before the supervised class has enough data. This is the skill's two-track rule (§3).

**Q2 — class granularity?** → **Class = `defect_criterion`**, NOT component type. The model learns the defect morphology (shared across components). Component type/package is carried as **metadata** for stratification + for routing the anomaly copy to the right per-component `ng/`. Exception: `wrong_value` is an OCR/OCV-vs-BOM problem, not a YOLO bbox class (see Q4).

**Q3 — 100-floor + 400 real + 1000 synthetic + Focal Loss?** → Sound and citable (Meng et al., ref §4; ~100/class floor from labeling playbook §10). Synthetic-amenability differs per criterion (drives whether to lean on `--generate-synthetic` or require a real floor):
- **Synthetic-amenable** (composite/geometric on good boards): `missing_component` (erase/place), `misalignment` (shift), `solder_short` (composite bridges), `wrong_value` (marking swap, OCR-side).
- **Partially** (geometric but the asymmetric marker must stay realistic): `orientation`, `polarity_flip`, `missing_pin_connector` (missing pin = erase ok).
- **Must be real** (2D synthetic unreliable): `lifted_pin` (height/3D, dark-field glint signature), `connector_pin_bending` (fine deformation).

**Q4 — which are fundamentally anomaly (good-vs-not), not supervised-class?** → `connector_pin_bending` + `missing_pin_connector` (matrix best = **EfficientAD anomaly**, AUROC~99%, <2 ms on the repetitive pin pattern); `lifted_pin` (anomaly good-only / **3D-required** — honest 2D limit). `wrong_value` → **OCR track**, neither YOLO-class nor anomaly. The rest (`missing_component`, `orientation`, `polarity_flip`, `misalignment`, `solder_short`) → supervised YOLO primary.

### 3.1 Routing table (the contract's core — derived from `defect_detector_mapping.yaml`)

| criterion | primary track | also feeds | YOLO class? | synthetic | honest limit |
|---|---|---|---|---|---|
| `missing_component` | supervised YOLO | anomaly `ng/` | yes (`missing_component`) | yes | — |
| `orientation` | supervised YOLO | OCR cross-check | yes | partial | marker realism |
| `polarity_flip` | supervised YOLO | OCR cross-check | yes | partial | marker realism |
| `misalignment` | supervised YOLO / template | anomaly `ng/` | yes | yes | — |
| `solder_short` (whole_side) | supervised YOLO+CBAM | anomaly whole-side | yes | yes | X-ray for hidden |
| `wrong_value` | **OCR/OCV vs BOM** | YOLO presence | **no** | text-swap | not a trained bbox class |
| `connector_pin_bending` | **anomaly (EfficientAD)** | YOLO secondary | optional | **no — real** | fine deformation in 2D |
| `missing_pin_connector` | anomaly / YOLO fine-grained | pin-count rule | optional | partial | — |
| `lifted_pin` | **anomaly good-only / 3D** | YOLO-on-depth | no | **no — real** | **3D defect; 2D under-promises** |

Derivation rule (**lives in `auto-inspect-service`** per operator decision 2026-05-31 — see §7.1):
- criterion mapped to `yolo*` detector → emit a **supervised crop** (YOLO images/+labels, class = criterion).
- criterion mapped to `anomalib*` detector → emit an **anomaly `ng/` crop** for that component.
- criterion mapped to `ocr` → mark **out-of-band** (feeds OCR/BOM config, not a trained crop class); do NOT fabricate a YOLO class.
- `lifted_pin` / `connector_pin_bending` → emit anomaly `ng/`; attach a **3D/real-data honest-limit flag** in the response so the UI can warn rather than over-promise.

The service's routing table MUST stay consistent with our `data/defect_detector_mapping.yaml` (which drives pipeline-planning presets). Both derive from the same 9 canonical criteria; drift mitigation in §7.1.

---

## 4. Proposed ingest contract

### 4.1 New endpoint on `auto-inspect-service`
```
POST /setup/{model_name}/defect-examples        # bearer-gated to match our other mutations
Content-Type: multipart/form-data
  - crop:        UploadFile        # the ROI image bytes (PNG/JPG)
  - criterion:   str              # one of the 9 canonical criteria — service derives the track from this
  - component:   str              # designator or component group (maps to {component}/ dir)
  - bbox:        str | None       # "x,y,w,h" normalized 0-1, required for supervised YOLO label
  - side:        str = "top"      # top | bottom
  - source_id:   str | None       # our defect_example UUID, for idempotency / dedup
Returns (service envelope):
  { written: [{track, path}], skipped_reason?: str, honest_limit?: str }
```
Behavior (new `services/setup_defects.py`, mirrors `crop_and_save` style):
- The **service** resolves the track from `criterion` via its own routing rule (`resolve_defect_track`, §3.1). The editor sends only `criterion` — no `track` param (operator decision §7.1).
- supervised → write `crop` to `dataset/{model}/_yolo/images/{source_id}.png` + a YOLO label line to `…/labels/{source_id}.txt` using `bbox` and a class-id from a per-model `defect_classes.txt` (criterion→id, created/extended idempotently).
- anomaly → write `crop` to `dataset/{model}/{component}/ng/{source_id}.png`.
- `wrong_value` / ocr-only → `skipped_reason="ocr_out_of_band"` (no crop class written).
- idempotent on `source_id` (overwrite, don't duplicate).

### 4.2 What the Visual Editor sends (new `services/inspect_service/defect_push.py`)
- Reads promoted `defect_examples` for a project (status=promoted, has ROI + criterion).
- POSTs each to the service endpoint above with `criterion` + `bbox` + `component` + `side`, carrying our `defect_example.id` as `source_id`. **The editor does NOT compute the track** — the service owns that mapping.
- New route `POST /api/projects/{id}/defect-examples/push` (bearer-gated) → returns a per-example push report. Surfaced on the S8 Datasets defect-library card ("N pushed to trainer / M skipped (OCR) / K need real 3D data").

### 4.3 Why a thin new endpoint vs reusing `/crop`
`/crop` hard-codes `good/` and needs a `components_manifest.yaml` + full frame. Our defect_examples are *already-cropped ROIs with a known criterion* — a purpose-built `defect-examples` endpoint is simpler, idempotent, and routes per criterion. The `/dataset/{component}/images/{f}/move` primitive confirms ng/ is a first-class label, so we are not inventing layout.

---

## 5. Data Integration Map

| Feature | Data source | Exists? | Action |
|---|---|---|---|
| Promoted escapes | our `defect_examples` table (migration 0012) | Yes | Read directly |
| criterion→track routing | `src/.../data/defect_detector_mapping.yaml` | Yes | Derive track from presets |
| Dataset dir layout | service `_resolve_dataset_dir` + `{component}/{label}/` | Yes | Write into it |
| ng/ label primitive | service `move_dataset_image` (good↔ng) | Yes | Same dir, direct write |
| YOLO images/labels | service `run_train_yolo` consumes images/+labels/ | Yes | Write YOLO label lines |
| Synthetic augmentation | engine `generate_synthetic_dataset` | Yes | Trigger via existing `--generate-synthetic` |
| Defect ingest endpoint | service `/setup/{model}/defect-examples` | **No** | **Create (Phase S-2)** |
| Push client + route | our `defect_push.py` + `/api/projects/{id}/defect-examples/push` | **No** | **Create (Phase V-2)** |

No placeholders. Every "Yes" is wired to real code read on 2026-05-31.

---

## 6. Phased TDD plan (cross-repo)

Each phase: write failing test → see expected failure → implement → green → commit. Service repo (`alisadikinma/auto-inspect-service`) and Visual Editor are separate commits.

### Service side (`auto-inspect-service`)
- **S-1 Routing rule + classes file.** Test: `resolve_defect_track("missing_component") == "supervised"`, `("lifted_pin")=="anomaly"+honest_limit`, `("wrong_value")=="ocr_out_of_band"`. Implement `services/setup_defects.py::resolve_defect_track` + `_class_id_for(model, criterion)` (idempotent `defect_classes.txt`).
- **S-2 Write crop per track.** Test (tmp storage dir): supervised → `_yolo/images/{id}.png`+`labels/{id}.txt` with correct class-id + bbox line; anomaly → `{component}/ng/{id}.png`; ocr → nothing written, `skipped_reason`. Implement `ingest_defect_example(...)`.
- **S-3 Endpoint.** Test via httpx ASGITransport: `POST /setup/{model}/defect-examples` multipart → 200 envelope, file on disk, idempotent on `source_id` (second post overwrites, count stays 1). Implement route in `routes/api/setup.py`.
- **S-4 (optional) honest-limit surfacing.** Test: `lifted_pin`/`connector_pin_bending` response carries `honest_limit`. Implement flag.

### Visual Editor side (`indusia-visual-editor`)
- **V-1 Track resolver from mapping.** Test: `resolve_track(criterion)` reads `defect_detector_mapping.yaml`, matches the routing table §3.1 for all 9 criteria. Implement in `services/inspect_service/defect_push.py`.
- **V-2 Push client.** Test (respx/httpx mock of the service): reads promoted `defect_examples`, POSTs each with `source_id`, aggregates a report; ocr-only criteria counted as skipped. Implement `push_defect_examples(project_id)`.
- **V-3 Route.** Test (ASGITransport, bearer-gated, DB-seeded promoted examples): `POST /api/projects/{id}/defect-examples/push` → `{status, message, data:{pushed, skipped, needs_real_data}}`. Implement route + register in `main.py`.
- **V-4 FE wiring.** Vitest: Datasets S8 card shows push button + report counts; MSW handler. (UI strings Bahasa Indonesia.)

### Integration (opt-in, env-gated like existing `IVE_*_SPIKE`)
- **I-1** End-to-end against a live local `auto-inspect-service`: push → assert files land → `POST /training/jobs` consumes them. Skipped unless `IVE_INSPECT_SERVICE_URL` set.

---

## 7. Honest limits / open decisions (need operator nod)

1. **Where does the routing rule live? RESOLVED 2026-05-31 → service side.** Operator chose the routing rule lives in `auto-inspect-service` (`resolve_defect_track`); the editor sends only `criterion`. **Drift risk:** the service's routing must stay consistent with our `data/defect_detector_mapping.yaml` (which drives pipeline-planning presets). Mitigation: (a) both derive from the same 9 canonical criteria; (b) add a service-side test that asserts every criterion maps to a known track; (c) document the pairing in both repos' CLAUDE.md so a criterion added in one is added in the other.
2. **`lifted_pin` / `connector_pin_bending` in 2D are the honest ceiling.** The contract routes them to anomaly + flags `honest_limit`; it does NOT promise a supervised 2D YOLO will catch them. Real-data floor + (eventually) dark-field/3D is the correct fix — surfaced to the operator, not hidden.
3. **`wrong_value` is deliberately not a trained crop class** — it's OCR-vs-BOM. The push reports it as skipped-OCR so the count isn't mistaken for a gap.
4. **Synthetic augmentation stays a service-side Gate-1 choice**, not auto-run by the push. The push only deposits real crops; the operator triggers `--generate-synthetic` at training time.
5. **Bearer-gating the new service endpoint** — the service currently uses its own auth posture; confirm we add the same gate we use elsewhere or match the service's existing scheme.

---

## 8. Next step

If approved: execute **S-1 → S-4** (service) then **V-1 → V-4** (editor) via gaspol-execute TDD, separate commits per repo, push to the respective `alisadikinma/*` mains. I will re-consult `ai-visual-inspection-expert` at any step where a routing or threshold judgment is in question.

---

## Implementation Plan

> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations against code read on 2026-05-31. During execution, NEVER substitute placeholders for real data sources without explicit user approval. If a data source doesn't exist yet, STOP and ask.

### Goal

Make operator-confirmed `defect_examples` (an ROI crop + one of 9 defect criteria) flow from the Visual Editor into `auto-inspect-service`'s existing dataset/training pipeline, routed to the correct detector track **by the service**, so the next supervised/anomaly retrain actually consumes them. Closes the last open half of the v1 inspection-feedback loop. Live edge-push stays out (v1.5).

### Architecture Context

**Two repos, separate commits, both owned by alisadikinma (PT Indusia):**

- **Receiver — `auto-inspect-service` v0.6.0** (`~/Drive-D/Projects/Indusia-Inspection/auto-inspect-service`). Verified conventions (inspect again at execution — do NOT assume the editor's):
  - Routes return **bare dicts**, NOT a `{status,message,data}` envelope (e.g. `routes/api/setup.py:125`). Match this.
  - Setup routes are **unauthenticated** (no `Depends`/`Security`/`Bearer` on `routes/api/setup.py`). The new endpoint matches that posture — do **not** bolt on the editor's bearer gate service-side.
  - Tests: `tests/unit/` + `tests/integration/`, `pytest` with fixtures in `tests/conftest.py` (`temp_dir`, `test_storage_dir`, `test_models_dir`, `test_config`, `sample_image_bytes`, `sample_upload_file`). Use the service's existing app-client fixture / transport as found in conftest — match it, don't introduce a different one.
  - Dataset layout (consumed by trainer): `storage/dataset/{model}/{component}/{label}/*.png`, `label ∈ {good,ng,train,test}`; YOLO = `images/`+`labels/`. Helper `services/setup_dataset.py::_resolve_dataset_dir`. Crop-write precedent: `crop_and_save` (same file). Move primitive: `move_dataset_image`.
  - Config dep: `ConfigDep` (FastAPI dependency) carries `AppConfig` with `.storage_dir`, `.models_dir`, `.discover_models()`.
- **Sender — `indusia-visual-editor`** (this repo). Conventions per CLAUDE.md: §5 layout (`services/inspect_service/` already exists for the httpx client to the service), §6 `{status,message,data}` envelope via `utils/responses.py`, async SQLAlchemy + `get_session`, exception handlers, **bearer-gated** mutations (`services/auth/dependencies.get_current_user`), structlog `get_logger`, OTel manual span on outbound boundaries. Tables `defect_examples` + `inspection_feedback` (migration `0012`). Tests: pytest-asyncio (auto) + httpx `ASGITransport`, DB-gated via `IVE_DATABASE_URL`, `tests/conftest.py` overrides `get_current_user` with a synthetic admin. FE: Pinia + axios + MSW + Vitest; Datasets S8 card already renders `GET /api/defect-examples/summary`.

### Tech Stack

Service: FastAPI, opencv (`cv2`), PyYAML, pytest. Editor: FastAPI async, httpx.AsyncClient, SQLAlchemy 2 async, pydantic v2, pytest-asyncio + httpx ASGITransport; FE Vue 3 + Pinia + axios + vue-i18n + Vitest + MSW.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Promoted escapes | `defect_examples` table (migration 0012) | SQLAlchemy `get_session` | Yes | Read directly (sender) |
| Promoted-example query | `services/feedback/*` (S7/S8) | existing CRUD | Yes | Reuse / extend list-by-status |
| Dataset dir resolve | service `_resolve_dataset_dir` | import in service | Yes | Call it (receiver) |
| ng/ label write | service `{component}/ng/` (per `move_dataset_image`) | filesystem | Yes | Write crop there |
| YOLO images/labels | service `run_train_yolo` consumes `images/`+`labels/` | filesystem | Yes | Write crop + label line |
| criterion→track rule | NEW service `resolve_defect_track` | service module | **No** | **Create (S-1)** |
| defect-classes id map | NEW service `defect_classes.txt` per model | filesystem | **No** | **Create (S-1/S-2)** |
| Defect ingest endpoint | NEW `POST /setup/{model}/defect-examples` | service route | **No** | **Create (S-3)** |
| Outbound push client | NEW `services/inspect_service/defect_push.py` | httpx.AsyncClient | **No** | **Create (V-2)** |
| Push route | NEW `POST /api/projects/{id}/defect-examples/push` | FastAPI bearer-gated | **No** | **Create (V-3)** |
| S8 push UI + report | `DatasetsView.vue` defect-library card | Pinia + axios + MSW | Partial | Extend (V-4) |

No placeholders. Every "Yes" maps to code read on 2026-05-31.

---

### Phase S-1: Service routing rule + defect-classes id map

**Repo:** `auto-inspect-service`  **Estimated time:** 12 min

**Files:**
- Create: `src/auto_inspect_service/services/setup_defects.py`
- Test: `tests/unit/test_setup_defects_routing.py`

**Steps:**
1. Write failing test for `resolve_defect_track`. Expected error: `ImportError: cannot import name 'resolve_defect_track' from 'auto_inspect_service.services.setup_defects'`. Assert: `missing_component→"supervised"`, `orientation→"supervised"`, `polarity_flip→"supervised"`, `misalignment→"supervised"`, `solder_short→"supervised"`, `connector_pin_bending→"anomaly"`, `missing_pin_connector→"anomaly"`, `lifted_pin→"anomaly"`, `wrong_value→"ocr_out_of_band"`; unknown criterion → `ValueError`.
2. Run test, confirm the ImportError.
3. Implement `resolve_defect_track(criterion: str) -> str` with a module-level `_CRITERION_TRACK` dict over the 9 canonical criteria (mirrors editor `data/defect_detector_mapping.yaml` §3.1). Add `_HONEST_LIMIT = {"lifted_pin","connector_pin_bending"}` and `honest_limit_for(criterion) -> str | None`. Add `class_id_for(model_dir, criterion) -> int` that reads/extends a per-model `defect_classes.txt` (idempotent: append criterion if new, return its 0-based line index).
4. Run tests, confirm all pass.
5. Commit (in service repo): `feat(defects): criterion→track routing + per-model defect-class id map`.

**Verification:**
- [ ] All 9 criteria + unknown-raises asserted green.
- [ ] `class_id_for` returns stable ids across calls (idempotent), new criterion appends.
- [ ] Routing matches §3.1 exactly; re-checked against `ai-visual-inspection-expert` routing table.
- [ ] No placeholder/TODO; matches service bare-dict/no-auth conventions.

### Phase S-2: Write crop per track (filesystem)

**Repo:** `auto-inspect-service`  **Estimated time:** 15 min

**Files:**
- Modify: `src/auto_inspect_service/services/setup_defects.py`
- Test: `tests/unit/test_setup_defects_ingest.py`

**Steps:**
1. Write failing test for `ingest_defect_example(...)` using `test_config` + `sample_image_bytes`. Expected error: `AttributeError`/`ImportError` (function absent). Assert three cases: supervised criterion → file at `dataset/{model}/_yolo/images/{source_id}.png` **and** `…/labels/{source_id}.txt` whose single line is `{class_id} {cx} {cy} {w} {h}` from the normalized bbox; anomaly criterion → file at `dataset/{model}/{component}/ng/{source_id}.png`; `wrong_value` → nothing written, returns `{"written": [], "skipped_reason": "ocr_out_of_band"}`.
2. Run test, confirm failure.
3. Implement `ingest_defect_example(model_name, crop_bytes, criterion, component, bbox, side, source_id, config) -> dict`: resolve track via S-1, resolve dataset root via existing `_resolve_dataset_dir`, decode+write crop with `cv2` (mirror `crop_and_save`), write YOLO label when supervised (require `bbox`, else `ValueError`), attach `honest_limit` when applicable. Idempotent on `source_id` (overwrite same path).
4. Run tests, confirm pass.
5. Commit: `feat(defects): write defect crop to ng/ or YOLO images+labels per track`.

**Verification:**
- [ ] Supervised writes both image + label with correct class-id + bbox line.
- [ ] Anomaly writes to `{component}/ng/`.
- [ ] OCR criterion writes nothing, reports `skipped_reason`.
- [ ] Re-posting same `source_id` does not duplicate (count stays 1).
- [ ] `lifted_pin`/`connector_pin_bending` carry `honest_limit` in the result.

### Phase S-3: Endpoint `POST /setup/{model}/defect-examples`

**Repo:** `auto-inspect-service`  **Estimated time:** 12 min

**Files:**
- Modify: `src/auto_inspect_service/routes/api/setup.py`
- Test: `tests/integration/test_defect_examples_endpoint.py`

**Steps:**
1. Write failing test hitting the route via the service's existing app-client fixture (multipart: `crop` file + `criterion`+`component`+`bbox`+`side`+`source_id` form fields). Expected error: `404` (route not registered). Assert 200 + bare dict `{"written":[...]}`, file on disk, and idempotency (second identical post → still one file).
2. Run test, confirm 404.
3. Implement `@router.post("/{model_name}/defect-examples")` async handler mirroring `crop_endpoint` (UploadFile + Form), calling `ingest_defect_example`, returning its dict. Match the service's bare-dict + unauthenticated posture. Map `ValueError`→422, `ModelNotFoundError`/`ConfigurationError`→ existing handlers.
4. Run tests, confirm pass.
5. Commit: `feat(defects): POST /setup/{model}/defect-examples ingest endpoint`.

**Verification:**
- [ ] 200 + crop on disk in the track-correct path.
- [ ] Idempotent on `source_id`.
- [ ] Missing `bbox` on a supervised criterion → 422.
- [ ] No auth added (matches sibling setup routes); bare dict response.

### Phase S-4: Honest-limit + classes-consistency guard

**Repo:** `auto-inspect-service`  **Estimated time:** 8 min

**Files:**
- Test: `tests/unit/test_setup_defects_consistency.py`
- Modify: `src/auto_inspect_service/services/setup_defects.py` (only if guard helper needed)

**Steps:**
1. Write failing test asserting (a) the routing table covers EXACTLY the 9 canonical criteria (no missing/extra) and (b) `honest_limit_for("lifted_pin")` is a non-empty Bahasa/English operator string while `honest_limit_for("missing_component")` is `None`. Expected error: `AssertionError`/`AttributeError`.
2. Run, confirm failure.
3. Implement `CANONICAL_CRITERIA` frozenset + a `assert_routing_complete()` used by the test; finalize `honest_limit_for` strings.
4. Run, confirm pass.
5. Commit: `test(defects): lock routing completeness + honest-limit flags`.

**Verification:**
- [ ] Routing covers the 9 criteria exactly (drift guard).
- [ ] honest-limit present only for the 2 flagged criteria.

### Phase V-1: Editor — promoted-examples reader

**Repo:** `indusia-visual-editor`  **Estimated time:** 10 min

**Files:**
- Create: `src/indusia_visual_editor/services/inspect_service/defect_push.py`
- Test: `tests/services/inspect_service/test_defect_push_reader.py`

**Steps:**
1. Write failing test for `list_promotable_examples(session, project_id)`. Expected error: `ImportError`. DB-gated (skip if no `IVE_DATABASE_URL`). Seed 2 promoted `defect_examples` (with ROI path + criterion) + 1 non-promoted; assert only the 2 promoted, each carrying `criterion`, `roi_path`, `component`/designator, `side`, `id`.
2. Run, confirm failure.
3. Implement the async reader querying `defect_examples` joined as needed (reuse existing feedback CRUD where possible).
4. Run, confirm pass.
5. Commit: `feat(defects): read promotable defect_examples for trainer push`.

**Verification:**
- [ ] Only promoted-with-ROI rows returned, fields complete.
- [ ] DB-gated test skips cleanly without Postgres.

### Phase V-2: Editor — push client to the service

**Repo:** `indusia-visual-editor`  **Estimated time:** 14 min

**Files:**
- Modify: `src/indusia_visual_editor/services/inspect_service/defect_push.py`
- Test: `tests/services/inspect_service/test_defect_push_client.py`

**Steps:**
1. Write failing test for `push_defect_examples(session, project_id, *, client_factory)` mocking the service HTTP (respx or a fake httpx transport). Expected error: `AttributeError`/`ImportError`. Assert: one multipart POST per promotable example to `{IVE_INSPECT_SERVICE_URL}/setup/{model}/defect-examples` carrying `criterion`+`bbox`+`component`+`side`+`source_id=<example.id>` and the ROI bytes; aggregates `{pushed, skipped, needs_real_data, errors}` where the service's `skipped_reason="ocr_out_of_band"` → `skipped`, `honest_limit` present → `needs_real_data`.
2. Run, confirm failure.
3. Implement using `httpx.AsyncClient` (NOT requests), wrap outbound in an OTel manual span `inspect_service.push_defect_examples`, raise `InspectServiceError` on transport failure. The editor sends **criterion only** — no track (service owns routing).
4. Run, confirm pass.
5. Commit: `feat(defects): httpx push client for defect_examples → auto-inspect-service`.

**Verification:**
- [ ] One POST per example; payload carries criterion (not track) + source_id.
- [ ] Report buckets pushed/skipped(OCR)/needs_real_data(honest-limit)/errors.
- [ ] Transport failure → `InspectServiceError`; OTel span present.

### Phase V-3: Editor — bearer-gated push route

**Repo:** `indusia-visual-editor`  **Estimated time:** 12 min

**Files:**
- Modify: `src/indusia_visual_editor/routes/deploy.py` (or new `routes/defect_examples.py`) + register in `main.py`
- Test: `tests/routes/test_defect_examples_push.py`

**Steps:**
1. Write failing test for `POST /api/projects/{id}/defect-examples/push` via httpx ASGITransport. Expected error: `404`. DB-gated; seed promoted examples; mock the outbound service client via the same test-seam factory pattern used by `routes/llm.py`/`routes/chat.py` (`set_*_client_factory`). Assert 200 + `{status, message, data:{pushed, skipped, needs_real_data}}` envelope, and that the route is bearer-gated (no token → 401, mirroring `tests/routes/test_auth_middleware.py`).
2. Run, confirm 404.
3. Implement the route: `dependencies=[Depends(get_current_user)]`, call `push_defect_examples`, return via `success(...)`. Add a `set_defect_push_client_factory`/`reset_*` test seam mirroring existing services.
4. Run, confirm pass.
5. Commit: `feat(defects): bearer-gated push route + test seam`.

**Verification:**
- [ ] 200 envelope `{status,message,data}`; 401 without bearer.
- [ ] Outbound client injected via factory seam (no real network in unit test).
- [ ] Registered in `main.py`; DB-gated test skips without Postgres.

### Phase V-4: Editor FE — S8 push action + report

**Repo:** `indusia-visual-editor`  **Estimated time:** 14 min

| Phase | Code Deliverable | Design Deliverable | Verification |
|---|---|---|---|
| V-4 | push button + report counts on Datasets S8 card | Reuse existing S8 card tokens (§A.6); Bahasa Indonesia copy; no new Figma surface | Vitest + MSW + i18n keys |

**Files:**
- Modify: `web/src/api/inspectionFeedback.ts` (add `pushDefectExamples(projectId)`), `web/src/stores/datasets` or `useInspectionFeedbackStore` (add action + report state), `web/src/views/DatasetsView.vue` (S8 card button + counts), `web/src/i18n/locales/{en,id}.json` (datasets namespace keys), `web/src/mocks/handlers.ts` (push handler)
- Test: `web/tests/unit/views/DatasetsView.defectPush.spec.ts` (or store spec)

**Steps:**
1. Write failing test for the push action/render. Expected error: test runner cannot find `pushDefectExamples` / the button `data-testid="datasets-defect-push"`. Assert: clicking calls the API, store records `{pushed, skipped, needs_real_data}`, card renders the three counts with Bahasa Indonesia labels; needs_real_data shows the honest-limit note ("butuh contoh nyata / 3D").
2. Run, confirm failure.
3. Implement api fn + store action + DatasetsView card button/counts + i18n keys + MSW handler. UI strings Bahasa Indonesia, no emoji, framed "dikirim ke trainer; retrain dipicu manual di Gate 1".
4. Run `vitest`, `vue-tsc`, confirm pass.
5. Commit: `feat(fb): push defect-library to trainer from Datasets S8 card`.

**Verification:**
- [ ] `vue-tsc` + `eslint` clean; `vitest` green.
- [ ] Card shows real counts from the push response (no fabricated numbers).
- [ ] Bahasa Indonesia copy; honest-limit note shown for needs_real_data.

### Phase I-1: Opt-in end-to-end integration (no new code, gated)

**Repo:** `indusia-visual-editor`  **Estimated time:** 10 min

**Files:**
- Test: `tests/integration/test_defect_push_e2e.py` (skipped unless `IVE_INSPECT_SERVICE_URL` set, like existing opt-in Ollama/inspect tests)

**Steps:**
1. Write failing test (skipped without env) that, against a live local `auto-inspect-service`, pushes seeded examples → asserts files land under `storage/dataset/{model}/...` → optionally `POST /training/jobs` accepts them. Expected error (when enabled): connection/404 until S-1..V-3 done.
2. Run with env set locally, confirm failure then pass after wiring.
3. (No production code — wiring only.)
4. Confirm skip path is clean without env.
5. Commit: `test(defects): opt-in e2e push→service integration`.

**Verification:**
- [ ] Skips cleanly without `IVE_INSPECT_SERVICE_URL`.
- [ ] With env: crops land in the service dataset dir, training job accepts the data dir.

---

### Execution order & commit/push discipline

- **Service repo first** (S-1→S-4): commit per phase, push to `alisadikinma/auto-inspect-service` `main` via `git -c credential.helper=osxkeychain push origin main` (token NOT in URL — see memory `sibling-repos-migrated`).
- **Editor repo** (V-1→V-4, I-1): commit per phase, push to `indusia-visual-editor` `main` (GPG-signed, never `--no-verify`).
- Re-consult `ai-visual-inspection-expert` before S-1 routing finalization and before any threshold/label-format judgment.
- After V-3 ships: update CLAUDE.md §16.1 (new editor route) + the service's CLAUDE.md (new endpoint + routing rule), per §17 update protocol.

### Execution handoff

- **Option 1 (this session):** start Phase S-1 via gaspol-execute, per-phase checkpoints + TDD hard gate.
- **Option 2 (parallel):** S-phases and V-1/V-2 have a contract dependency (V-2's mock must match S-3's shape), so run S-1→S-3 first, then V-1→V-4 can parallelize with care. Not recommended to fully parallelize across the contract boundary.
- **Option 3 (separate session):** this doc is self-contained; resume from Phase S-1.
