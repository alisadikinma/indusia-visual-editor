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
