# G5 — Stable held-out eval split (design + cross-repo TDD plan)

> **For Claude:** REQUIRED SKILL: Use gaspol-execute to implement this plan.
> **CRITICAL:** This plan specifies real integrations against code read on 2026-05-31. During
> execution, NEVER substitute placeholders for real data sources without explicit user approval.
> If a data source doesn't exist yet, STOP and ask. One such gap is already flagged below
> (crop OUTPUT drops the existing `_f{n}` board/frame provenance — see §Flagged decision).
> **Status:** design approved + inspection-expert-validated. NO production code yet.
> **Date:** 2026-05-31
> **Scope:** cross-repo — `auto-inspect-engine` (heart) + `auto-inspect-service` (thin) +
> `indusia-visual-editor` (thin). All three owned by alisadikinma / PT Indusia.
> **Inspection-domain gate:** validated against `ai-visual-inspection-expert` SKILL.md §3/§5/§9/§10.

---

## Design

### Goal

Make the train/test split **stable across retrains** so Gate-2 promote metrics (mAP / F1 macro /
per-component F1) are comparable run-to-run. Today they are not: the split is re-derived on every
dataset-prep run and silently reshuffles when data grows.

### Problem (verified in code 2026-05-31)

The split lives in `auto-inspect-engine`, not the editor. Two failure modes break stability:

1. **Unsorted read.** `prepare_anomaly_dataset` re-reads `test/good/` via `good_test_dir.iterdir()`
   (`auto-inspect-engine/src/auto_inspect_engine/utils/preprocessing.py` ~line 439) — filesystem
   order, not deterministic. (Note: `collect_image_paths` IS sorted at :77, but the good-split
   re-read at ~439 is NOT.)
2. **Position-based split.** `train_test_split(good_images, test_size=test_split, random_state=42)`
   (`preprocessing.py` ~445) is position-based, so **adding or removing one good image reshuffles the
   entire test membership.** `random_state=42` only guarantees reproducibility when the input list is
   byte-identical in content, count, and order.

Supplementary paths with the same fragility:
- `cli/train_yolo.py:21` `split_dataset(seed=42, split=0.8)` — `random.shuffle` + index slice;
  **train/val only, NO test set** (supervised Gate-2 F1 has no held-out test today).
- `cli/_data_dataset.py:15` `split_dataset` — operator 3-way 0.7/0.2/0.1, `stratify=True`, separate path.

There is **no manifest, no hash assignment, no locked split anywhere** (repo-wide grep nihil). The
split is encoded only by file location under `{component}/{train,test}/{good,ng,...}/`; label vocab on
disk = `good / ng / train / test / val` (MVTec layout). Crops are named `{comp_name}_{idx:05d}.png`
(`auto-inspect-service/.../services/setup_dataset.py:752`).

### Design decisions (inspection-expert-validated — do not re-litigate)

| # | Decision | Grounding |
|---|---|---|
| a | Ratio **70/15/15** default; enforce an **absolute test floor ≥ 20–30 per defect class**. Below floor → emit `unstable: true` + reason, do NOT report a misleading F1. | SKILL §10 (stable 70/15/15), §5 (~100/class floor) |
| b | Split **UNIT = per physical board/frame (GROUP split)**, not per crop — all crops from one board land on one side (anti-leakage). **BLOCKED today** — see §Flagged decision. Core stability ships per-image-hash first; group key (by **board**, via the existing `_f{n}` provenance) layered once crop output carries it. | SKILL §10 (held-out stable), §9 (domain shift) |
| c | **Stratify by `defect_criterion`** so each class is represented in test; class with 0 test examples → cannot measure per-comp F1 0.70 → surface "data test kurang untuk kriterion X". | SKILL §5/§10 (class imbalance, per-comp F1 0.70) |
| d | **Mechanism = deterministic hash `int(sha1(key+seed)) % 100 < test_pct` for default assignment + `split_manifest.json` (co-located in `output_dir`) for audit + manual override/pin.** Consult manifest first; only NEW keys get hash-assigned and appended. Fixes both failure modes (growth-stable, order-independent). | engine code reading 2026-05-31; standard group-hash partition |
| e | **Anomaly track:** `good` → train-good + **test-good (pinned)**; **ALL `ng` → test** (anomaly trains good-only). Pin `ng` membership in the manifest too; new `ng` flagged as "perluasan coverage sejak baseline" (recall absolute not comparable unless frozen). | SKILL §3 (anomaly good-only) |
| f | **Test set REAL-ONLY** (synthetic 400+1000 train-only); prevent synthetic↔real leak via the group key. Class 3 (medical) → recall-first, need enough escapes/class in test. | SKILL §5 (synthetic train-only), §9 (recall-first) |

### Flagged decision (provenance exists at INPUT, dropped at OUTPUT — gated)

Decision (b) group-by-board needs a board identifier on each crop. The provenance is **NOT missing
from the pipeline** — it is an existing convention: in graphflow-mode batch crop, the input frame
images are named `{board}_f{n}.png` and the frame is resolved from the `_f{n}` suffix (README.md:168
"Crop Input Data Format (Graphflow Mode)" + CLI.md:94; fallback = numbered folders). The gap is only
that the crop **output** loses it — `crop_and_save` saves `{comp_name}_{idx:05d}.png`
(`setup_dataset.py:752`), carrying neither board nor frame.

Critical distinction (drives the design): **`_f{n}` is the FRAME number, not the board.** The board
identity is the filename **prefix** (`board1` vs `board2`), and `board1_f0` / `board1_f1` are the
*same physical board*. So for anti-leakage the group key must be the **board prefix**, NOT `_f{n}`
(keying on `_f{n}` would wrongly merge `board1_f0` with `board2_f0`). The board prefix is available in
the **graphflow-mode batch** crop path (input filenames); the single-frame `POST /crop` upload only
receives `frame_id`, so that path has no board id and falls back to per-frame/per-stem.

Resolution (phased, no stub):
- **Phase group A (E-1..E-4)** ships the core stability fix keyed by **image stem** — fixes both
  failure modes and delivers the G5 goal (comparable metrics across retrains) on its own.
- **Phase group B (E-5..E-6, gated)** preserves the existing `_f{n}` provenance into the crop output
  and adds the board prefix, then keys the split by **board** for anti-leakage. Backward-compatible —
  old crops (no board/frame token) fall back to per-stem. **Execute B only after the operator confirms
  the crop-output-naming change** (it ripples to how existing datasets are re-read).

### Honest scope

G5 is **engine-heavy**. The "G5 in the editor" surface (S5 "Locked test set", Figma `179:68` EN /
`179:189` ID) is only a **display** of the split status the engine computes and the service exposes.

---

## Implementation Plan

### Architecture Context

**Three repos (separate commits, separate pushes):**

- **`auto-inspect-engine`** (`~/Drive-D/Projects/Indusia-Inspection/auto-inspect-engine`) — pure Python
  lib, no server. Split logic: `src/auto_inspect_engine/utils/preprocessing.py`
  (`prepare_anomaly_dataset` :321, `collect_image_paths` :61 sorted), `cli/train_yolo.py`
  (`split_dataset` :21), `cli/_data_dataset.py` (`split_dataset` :15). Tests: **flat** `tests/test_*.py`
  (pytest; e.g. `tests/test_data_utils.py`). `requires-python = ">=3.10"`. RGB convention.
- **`auto-inspect-service`** (`~/Drive-D/Projects/Indusia-Inspection/auto-inspect-service`) v0.6.0 —
  FastAPI :8001, **no auth on setup routes**, routes return **bare dicts** (NOT `{status,message,data}`).
  Orchestration funnel: `services/setup_dataset.py` `prepare_training_data` → calls
  `prepare_anomaly_dataset(input_dir=comp_dir, output_dir=comp_dir, test_split=...)`. Crop write:
  `crop_and_save` :667 (names `{comp_name}_{idx:05d}.png` :752). Setup routes: `routes/api/setup.py`
  (`crop_endpoint` :524). Tests: `tests/unit/` + `tests/integration/`, fixtures `temp_dir` /
  `test_storage_dir` / `test_config` / `sample_image_bytes` in `tests/conftest.py`. Config dep
  `ConfigDep` with `.storage_dir` / `.models_dir`.
- **`indusia-visual-editor`** (this repo) — conventions per CLAUDE.md: `{status,message,data}` envelope
  (`utils/responses.py`), bearer-gated mutations (`services/auth/dependencies.get_current_user`), GETs
  public, async SQLAlchemy + `get_session`, structlog `get_logger`, OTel manual span on outbound
  boundaries. Eval read client: `web/src/api/eval.ts` (`getEval` → `/training/{runId}/eval`,
  `EVAL_THRESHOLDS`, `classifyEval`). SetupEvalView already has a test-set section
  (`testSetOptions = ['holdout','production_run','upload']`) + readiness `gates` + `useEvalStore`/
  `useTrainingStore`. FE: Pinia + axios over `apiClient` + MSW + Vitest + vue-i18n + §A.6 tokens.

### Tech Stack

Engine: Python 3.10+, opencv (`cv2`), numpy, scikit-learn (`train_test_split`), hashlib (stdlib),
json (stdlib), pytest. Service: FastAPI, PyYAML, pytest + httpx. Editor: FastAPI async + pydantic v2;
FE Vue 3.5 + Pinia 2 + axios + vue-i18n 10 + Vitest + MSW 2.

### Data Integration Map

| Feature | Data Source | Hook/API | Exists? | Action |
|---|---|---|---|---|
| Anomaly split decider | `preprocessing.prepare_anomaly_dataset` good-split block | engine import | Yes | Make manifest+hash-backed (E-2) |
| YOLO split decider | `train_yolo.split_dataset` | engine import | Yes (train/val) | Add held-out test + manifest (E-4) |
| Stable assignment fn | NEW `preprocessing.stable_assign(key, seed, test_pct)` | engine module | **No** | Create (E-1) |
| Split manifest schema | NEW `split_manifest.json` in `output_dir` | engine fs | **No** | Create (E-1/E-2) |
| Per-class test floor flag | NEW manifest field `unstable`/`reason` | engine | **No** | Create (E-3) |
| Crop board/frame id | crop filename `{comp_name}_{idx}.png` (no frame id) | `setup_dataset.crop_and_save` | **No** | **FLAGGED — gated E-5** |
| Group-split key | board/frame id from filename | engine | **No** | Gated on E-5 (E-6) |
| Split config threading | `prepare_training_data(test_split, seed, ...)` | service | Partial (`test_split`) | Extend (S-1) |
| Split-status read endpoint | NEW `GET /setup/{model}/split-status` | service route | **No** | Create (S-2) |
| Editor split-status client | NEW `web/src/api/split.ts` | apiClient | **No** | Create (V-1) |
| Editor split state | `useEvalStore` / `useTrainingStore` | Pinia | Partial | Extend (V-2) |
| S5 "Locked test set" UI | `SetupEvalView.vue` test-set section | Vue + i18n | Partial (holdout option) | Extend (V-3) |
| MSW split-status mock | `web/src/mocks/handlers.ts` | MSW | **No** | Create (V-3) |

No placeholders. Every "Yes/Partial" maps to code read on 2026-05-31. The one **No** that lacks a data
source (crop board/frame id) is gated behind operator confirmation in E-5, not stubbed.

---

## Phase group A — Core stability (engine, per-image-hash). Ships the G5 goal.

### Phase E-1: stable-assign helper + manifest schema

**Repo:** `auto-inspect-engine`  **Estimated time:** 12 min

**Files:**
- Modify: `src/auto_inspect_engine/utils/preprocessing.py` (add helpers near top)
- Test: `tests/test_stable_split.py`

**Steps:**
1. Write failing test for `stable_assign(key, seed, test_pct)`. Expected error:
   `ImportError: cannot import name 'stable_assign' from auto_inspect_engine.utils.preprocessing`.
   Assert: deterministic (same key+seed → same bucket across calls); `test_pct=15` puts ~15% of a
   1000-key sample in `"test"` (±3%); changing `seed` changes membership; key absent has no effect on
   other keys' buckets (growth-stability — assign 1000 keys, add 1 more, assert the original 1000
   buckets are unchanged).
2. Run test, confirm the ImportError.
3. Implement `stable_assign(key: str, seed: int, test_pct: int) -> str` using
   `int(hashlib.sha1(f"{key}:{seed}".encode()).hexdigest(), 16) % 100 < test_pct` → `"test"` else
   `"train"`. Add `load_split_manifest(output_dir) -> dict` / `save_split_manifest(output_dir, dict)`
   reading/writing `split_manifest.json` (`{"seed":..,"test_pct":..,"members":{key:"train|test"}}`),
   tolerant of a missing file (returns empty scaffold).
4. Run tests, confirm pass.
5. Commit (engine repo): `feat(split): deterministic stable-assign + split_manifest helpers`.

**Verification:**
- [ ] `stable_assign` deterministic + growth-stable (adding a key doesn't move others)
- [ ] manifest round-trips; missing file → empty scaffold, no crash
- [ ] No placeholder/TODO; matches engine style

### Phase E-2: manifest-backed stable split in `prepare_anomaly_dataset`

**Repo:** `auto-inspect-engine`  **Estimated time:** 15 min

**Files:**
- Modify: `src/auto_inspect_engine/utils/preprocessing.py` (`prepare_anomaly_dataset` good-split ~438-460)
- Test: `tests/test_stable_split.py` (extend)

**Steps:**
1. Write failing test (tmp dirs with N good images): call `prepare_anomaly_dataset` twice, then add 2
   new good images and call again. Expected error: `AssertionError` (current code reshuffles).
   Assert: (i) test-good membership identical across the first two runs; (ii) after adding 2 images,
   the ORIGINAL images keep their train/test bucket and only the 2 new ones get newly assigned;
   (iii) a `split_manifest.json` exists in `output_dir` recording members + seed + test_pct.
2. Run, confirm failure (reshuffle / no manifest).
3. Implement: replace the unsorted `good_test_dir.iterdir()` read with a **sorted** listing; load the
   manifest; for each good image keyed by `path.stem`, use the manifest bucket if present, else
   `stable_assign(stem, random_state, int(test_split*100))` and append to the manifest; move train-bucket
   images to `train/good`, leave test-bucket in `test/good`; persist the updated manifest. Keep `ng`
   copied test-only (unchanged — decision e).
4. Run tests, confirm pass.
5. Commit: `feat(split): manifest-backed stable train/test for anomaly good set`.

**Verification:**
- [ ] Test membership stable across re-runs AND under data growth
- [ ] `ng` stays test-only; manifest written with seed/test_pct/members
- [ ] Existing `prepare_anomaly_dataset` callers unaffected (default args preserved)
- [ ] No placeholder/TODO

### Phase E-3: stratify guard + per-class test floor flag

**Repo:** `auto-inspect-engine`  **Estimated time:** 12 min

> Re-consult `ai-visual-inspection-expert` to confirm the floor number (20–30) before locking it.

**Files:**
- Modify: `src/auto_inspect_engine/utils/preprocessing.py`
- Test: `tests/test_stable_split.py` (extend)

**Steps:**
1. Write failing test: build a dataset where one defect class has 3 `ng` images and another has 40.
   Expected error: `AssertionError`/`KeyError` (no floor flag today). Assert the returned `stats`
   carries `per_class_test_counts` (dict criterion→count) and `unstable_classes` listing the class
   below the floor with a reason string; `stats["unstable"]` is `True` when any class is below floor.
2. Run, confirm failure.
3. Implement: add `min_test_per_class: int = 25` param; after assembly, count test members per class,
   populate `stats["per_class_test_counts"]`, `stats["unstable_classes"]` (`[{class, count, reason}]`),
   `stats["unstable"]`. Do NOT raise — surface the flag (operator decides at Gate). Stratification note:
   anomaly `ng` is already all-test (decision e), so the floor check is the stratify guarantee for the
   anomaly track; record the seed used.
4. Run tests, confirm pass.
5. Commit: `feat(split): per-class test-floor flag + counts in anomaly stats`.

**Verification:**
- [ ] `stats` exposes per-class test counts + unstable flag; never raises on low data
- [ ] Floor default 25 (re-confirmed with inspection-expert), overridable
- [ ] No placeholder/TODO

### Phase E-4: held-out TEST set + manifest for the YOLO track

**Repo:** `auto-inspect-engine`  **Estimated time:** 15 min

**Files:**
- Modify: `src/auto_inspect_engine/cli/train_yolo.py` (`split_dataset` :21)
- Test: `tests/test_stable_split.py` (extend) or `tests/test_train_yolo_split.py`

**Steps:**
1. Write failing test (tmp `images/`+`labels/` pairs): call `split_dataset` twice + once after adding a
   pair. Expected error: `AssertionError` (today shuffles, train/val only, no test, no manifest).
   Assert: a **three-way** train/val/test output exists; test membership stable across runs and under
   growth; `split_manifest.json` written; pairs keyed by `img_path.stem` stay grouped (image+label
   together).
2. Run, confirm failure.
3. Implement: add `val_frac`/`test_frac` (default 0.7/0.15/0.15) + manifest-backed assignment via
   `stable_assign(stem, seed, ...)`; write `train/`, `val/`, `test/` (images+labels) + `dataset.yaml`
   gaining a `test:` key; preserve back-compat default behavior behind the new params where reasonable.
4. Run tests, confirm pass.
5. Commit: `feat(split): stable 3-way held-out split + manifest for YOLO track`.

**Verification:**
- [ ] Train/val/test dirs produced; test stable across runs + growth; manifest written
- [ ] image+label stay paired in the same bucket
- [ ] `dataset.yaml` includes `test:`; no placeholder/TODO

---

## Phase group B — Group-by-board (GATED on operator confirm of crop-naming change)

> Do NOT start B until the operator approves the crop-output-naming change (ripples to how existing
> datasets are re-read). Until then, A's per-stem split is the shipped behavior. Follow the EXISTING
> `_f{n}` convention (README.md:168 / CLI.md:94) — do not invent a new delimiter.

### Phase E-5: preserve board+frame provenance into the crop output filename

**Repo:** `auto-inspect-service`  **Estimated time:** 14 min

**Convention to follow (existing):** graphflow-mode batch input is `{board}_f{n}.png`; frame resolved
from the `_f{n}` suffix. The output crop must carry the board id so the split can group by it. Target
output name: `{comp_name}__{board}_f{n}__{idx:05d}.png` (double-underscore delimiters bound the
`{board}_f{n}` provenance token so E-6 can extract it unambiguously even though comp/board contain
single underscores). The single-frame `POST /crop` path has no board → embed `f{frame_id}` only and,
absent a board, the group falls back to per-stem.

**Files:**
- Modify: `src/auto_inspect_service/services/setup_dataset.py` (`crop_and_save` ~752; and the batch
  `crop_from_directory` / graphflow-mode path in `services/setup_operations.py` ~477 which knows the
  source filename → board prefix)
- Test: `tests/unit/test_crop_naming.py`

**Steps:**
1. Write failing test for a pure naming helper `_crop_output_name(comp, board, frame, idx)` (extracted
   so it is importable without the graphflow chain): asserts `R1__board1_f0__00007.png` for
   `(comp="R1", board="board1", frame=0, idx=7)`, and `R1__f0__00007.png` when `board is None`. Expected
   error: `ImportError`/`AttributeError` (helper absent). (Helper-level test avoids needing graphflow to
   exercise full `crop_and_save`.)
2. Run, confirm failure.
3. Implement `_crop_output_name(...)` (sanitize tokens, `__`-bounded provenance segment) in a
   chain-free module; have `crop_and_save` use it with `board=None` (upload path) and the batch
   graphflow-mode crop derive `board` from the source filename prefix (strip the `_f{n}` suffix) and
   pass it through. Old files (plain `{comp}_{idx}`) keep listing/moving fine.
4. Run tests, confirm pass.
5. Commit (service repo): `feat(split): carry {board}_f{n} provenance into crop output filename`.

**Verification:**
- [ ] Helper emits `__{board}_f{n}__` when board known, `__f{n}__` when only frame, plain when neither
- [ ] Batch graphflow-mode crop derives board from the `_f{n}` input prefix; upload path degrades cleanly
- [ ] Old crops still listed/moved fine; no placeholder/TODO; bare-dict/no-auth conventions intact

### Phase E-6: key the split by BOARD id (anti-leakage), parsing the `_f{n}` provenance

**Repo:** `auto-inspect-engine`  **Estimated time:** 14 min

**Files:**
- Modify: `src/auto_inspect_engine/utils/stable_split.py` (add `group_key_for`), wire into
  `preprocessing.prepare_anomaly_dataset` + `cli/train_yolo.split_dataset`
- Test: `tests/test_stable_split.py` + `tests/test_anomaly_split.py` (extend)

**Steps:**
1. Write failing test: `group_key_for("R1__board1_f0__00007")` == `"board1"` and
   `group_key_for("C4__board1_f1__00002")` == `"board1"` (same board, different frame → SAME key);
   `group_key_for("R1__board2_f0__00001")` == `"board2"`; `group_key_for("R1__f0__00003")` ==
   `"f0"` (no board → frame token); `group_key_for("R1_00009")` == `"R1_00009"` (legacy → stem
   fallback). Plus an anomaly-split test: two good crops of the same board across frames land in the
   SAME bucket. Expected error: `ImportError` (`group_key_for` absent).
2. Run, confirm failure.
3. Implement `group_key_for(path) -> str`: extract the `__…__` provenance token; if it contains
   `{board}_f{n}` return the **board** prefix (strip the trailing `_f{n}`); if only `f{n}`, return that;
   else fall back to `path.stem`. Switch `prepare_anomaly_dataset` + `split_dataset` to key
   `stable_assign`/`stable_partition` + the manifest by `group_key_for(p)` instead of `p.stem`.
   Manifest `members` then keyed by board, so all crops of a board move together.
4. Run tests, confirm pass.
5. Commit: `feat(split): group-by-board split key (anti-leakage) via _f{n} provenance`.

**Verification:**
- [ ] Crops sharing a board (across frames) never split across train/test; different boards independent
- [ ] Frame-only and legacy names degrade correctly (frame token / stem)
- [ ] Manifest keyed by group; no placeholder/TODO
- [ ] Fallback to stem when id absent (old data); manifest keyed by group
- [ ] No placeholder/TODO

---

## Phase group C — Service threading + status endpoint (thin)

### Phase S-1: thread seed / test_split / floor through `prepare_training_data`

**Repo:** `auto-inspect-service`  **Estimated time:** 10 min

**Files:**
- Modify: `src/auto_inspect_service/services/setup_dataset.py` (`prepare_training_data`)
- Test: `tests/unit/test_prepare_training_data_split.py`

**Steps:**
1. Write failing test (using `test_config` + `test_storage_dir`): call `prepare_training_data` with
   `seed` + `test_split` + `min_test_per_class` and assert they reach `prepare_anomaly_dataset` and a
   `split_manifest.json` lands under each component dir. Expected error: `TypeError` (params not accepted).
2. Run, confirm failure.
3. Implement: add the params (defaults 42 / 0.15 test / 25 floor) and pass them through; aggregate any
   `unstable_classes` into the return dict.
4. Run tests, confirm pass.
5. Commit (service repo): `feat(split): thread seed/test_split/floor through training data prep`.

**Verification:**
- [ ] Params reach the engine; manifest present per component; unstable classes aggregated
- [ ] Bare-dict return; no auth added; flake8 clean

### Phase S-2: `GET /setup/{model_name}/split-status`

**Repo:** `auto-inspect-service`  **Estimated time:** 12 min

**Files:**
- Modify: `src/auto_inspect_service/routes/api/setup.py` (+ a reader in `setup_dataset.py`)
- Test: `tests/integration/test_split_status_endpoint.py`

**Steps:**
1. Write failing test (app-client fixture; seed a `split_manifest.json` on disk): `GET
   /setup/{model}/split-status` → 200 bare dict `{seed, test_pct, per_component:[{component,
   train_count, test_count, per_class_test_counts, unstable, unstable_classes}]}`. Expected error: 404.
2. Run, confirm 404.
3. Implement a reader that walks component dirs, loads each `split_manifest.json` + counts files in
   `train/`/`test/`, and a `@router.get("/{model_name}/split-status")` returning the aggregate (bare
   dict, unauthenticated — matches sibling setup routes). 404 when model unknown.
4. Run tests, confirm pass.
5. Commit: `feat(split): GET /setup/{model}/split-status read endpoint`.

**Verification:**
- [ ] 200 aggregate from real manifests; 404 unknown model
- [ ] No auth; bare dict; idempotent read

---

## Phase group D — Editor S5 "Locked test set" indicator (thin)

### Phase V-1: editor split-status api client

**Repo:** `indusia-visual-editor`  **Estimated time:** 8 min

**Files:**
- Create: `web/src/api/split.ts`; Test: `web/src/api/__tests__/split.spec.ts` (MSW)

**Steps:**
1. Write failing test: `getSplitStatus(modelName)` returns parsed `{seed, testPct, perComponent[...]}`
   from a mocked envelope. Expected error: module not found.
2. Run, confirm fail.
3. Implement typed `SplitStatus`/`ComponentSplit` interfaces + `getSplitStatus(modelName)` over
   `apiClient` unwrapping `data.data`. (The editor calls its OWN backend proxy if one is added, else the
   service directly — confirm at execution which base the editor uses for setup reads; if none exists,
   STOP and ask rather than hardcode `:8001`.)
4. Run, confirm pass.
5. Commit (editor repo): `feat(fb): split-status api client`.

**Verification:**
- [ ] `vue-tsc` clean; spec passes against MSW; no double `/api`
- [ ] Base URL resolved against an existing client, not a hardcoded sibling port

### Phase V-2: split state in store

**Repo:** `indusia-visual-editor`  **Estimated time:** 8 min

**Files:**
- Modify: `web/src/stores/eval.ts`; Test: `web/src/stores/__tests__/eval.split.spec.ts`

**Steps:**
1. Write failing test: `fetchSplitStatus(modelName)` populates `splitStatus` + a `belowFloor` getter
   (true when any component has `unstable`). Expected error: action undefined.
2. Run, confirm fail.
3. Implement `splitStatus` ref + `fetchSplitStatus` action + `belowFloor`/`lockedSeed` getters, error
   via `extractMessage` (mirror existing store pattern).
4. Run, confirm pass.
5. Commit: `feat(fb): eval store split-status state`.

**Verification:**
- [ ] store spec passes (fetch + belowFloor)
- [ ] error path sets `error`; no placeholder/TODO

### Phase V-3: SetupEvalView "Locked test set" indicator + i18n + MSW

**Repo:** `indusia-visual-editor`  **Estimated time:** 14 min

| Phase | Code Deliverable | Design Deliverable | Verification |
|---|---|---|---|
| V-3 | Locked-test-set indicator on SetupEvalView | Figma S5 `179:68`(EN)/`179:189`(ID) + §A.6 tokens; Bahasa Indonesia copy | vue-tsc + component test + token compliance |

**Files:**
- Modify: `web/src/views/SetupEvalView.vue`, `web/src/locales/en.json` + `id.json`,
  `web/src/mocks/handlers.ts`
- Test: `web/src/views/__tests__/SetupEvalView.split.spec.ts`

**Steps:**
1. Write failing test: when test-set option `holdout` is active, the view calls
   `evalStore.fetchSplitStatus` on mount and renders a locked badge with seed + total test count; when
   `belowFloor`, renders a warning listing classes below floor. Expected error:
   `data-testid="setupeval-locked-split"` not found.
2. Run, confirm fail.
3. Implement the indicator inside the existing `setupeval-testset` section (extend the `holdout`
   option): locked badge (seed, per-class test counts), amber warning when `belowFloor` ("data test
   kurang untuk kriterion: …"), using §A.6 tokens + `useI18n` keys under `setupEval.split.*`. Add MSW
   handler for `split-status`. Bahasa Indonesia copy, no emoji.
4. Run `vitest` + `vue-tsc --noEmit` + `eslint`, confirm pass.
5. Commit: `feat(fb): locked test-set indicator on SetupEvalView (S5)`.

**Verification:**
- [ ] `vue-tsc` + eslint clean; vitest green
- [ ] Indicator shows real seed/counts from `fetchSplitStatus` (no fabricated numbers)
- [ ] Below-floor warning lists real classes; Bahasa Indonesia copy; §A.6 tokens only

---

## Execution order & commit/push discipline

1. **Engine first** (E-1→E-4): commit per phase, push `alisadikinma/auto-inspect-engine` main.
2. **(Gated) Group-by-board** (E-5→E-6): ONLY after operator approves the crop-naming change.
3. **Service** (S-1→S-2): push `alisadikinma/auto-inspect-service` main.
4. **Editor** (V-1→V-3): push `indusia-visual-editor` main (GPG-signed, never `--no-verify`).
- Re-consult `ai-visual-inspection-expert` before locking the test floor (E-3) and before any
  threshold/stratify judgment.
- After V-3: update CLAUDE.md §16 (new editor api/store/view delta) + the service CLAUDE.md (new
  `split-status` endpoint + threaded params) + engine notes, per the §17 update protocol.

## Explicitly OUT of scope

- Drift re-eval (G3b) — separate gap; G5 is its prerequisite (locked split).
- Editor backend proxy for setup reads — if the editor has no existing path to the service for setup
  data, V-1 STOPS and asks rather than hardcoding `:8001`.
- Backfilling frame ids into already-saved crops — old crops fall back to per-stem (safe).
