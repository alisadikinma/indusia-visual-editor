# Graphflow Config Schema — Phase 0.2 Spike Report

> Status: **DOCUMENTED** — 2026-05-22
> Source: `D:\Projects\Indusia-Inspection\auto-inspect-service` (the existing inference engine we integrate with)
> Inputs to spike: `README.md` §2, `CLAUDE.md`, `templates/presets/*.yaml`, `schemas/node_params.yaml`
> Verifies: M4 (planner adapter) needs to emit this shape; M7 (training trigger) needs to write configs in this layout

---

## TL;DR

The auto-inspect-service consumes per-PCB pipelines as a **two-layer YAML tree**:

```
<models_dir>/<pcb_name>/
├── config.yaml          ← TOP-LEVEL: {name, nodes, edges}; alignment stage + subgraph refs
├── locations.yaml       ← inspection frames: list of {side, location, frame_id, unit}
├── settings.yaml        ← camera/luminance/gain/exposure config
├── components/          ← per-component subgraphs: {nodes, edges} only (NO name)
│   ├── comp-U7.yaml
│   └── comp-C4.yaml
└── assets/              ← template images, fiducials, golden references
```

Loader: `POST /api/models/{name}/load` reads `config.yaml` then walks `nodes[*].path` for subgraph includes, builds a `DirectedGraph`, registers under a UUID. See `auto-inspect-service/README.md` §2 line 104.

## 1. Top-level `config.yaml` schema

Exactly three top-level keys.

| Key | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | URL-safe pipeline identifier; matches `<pcb_name>` dir + API param |
| `nodes` | mapping(name → NodeDef) | yes | DAG vertex set; keys are node labels, values declare type + params |
| `edges` | mapping(source_name → target_name OR list[name]) | yes | DAG adjacency |

A `NodeDef` is `{type: <registered_type>, params?: {...}, path?: <subgraph.yaml>}`.

### `type: graph` — subgraph reference

Top-level configs use `type: graph` + `path: components/comp-X.yaml` to compose per-component subgraphs. The loader recursively resolves the path (relative to `config.yaml` parent).

```yaml
name: "board-NV7320H-1"
nodes:
  data:        { type: input }
  fiducial:    { type: fiducial_detector, params: { path: "assets/fiducial_TL.png" } }
  component-U7: { type: graph, path: "components/comp-U7.yaml" }
  component-C4: { type: graph, path: "components/comp-C4.yaml" }
  output:      { type: merge_result }
edges:
  data:        [ fiducial ]
  fiducial:    [ component-U7, component-C4 ]
  component-U7: [ output ]
  component-C4: [ output ]
```

## 2. Subgraph (component) yaml schema

Exactly two top-level keys: `nodes` and `edges`. **No `name`** — identifier is inherited from the parent's node label.

```yaml
nodes:
  data:         { type: input }
  preprocess:   { type: yolo_crop, params: { classes: "U7", expand_ratio: 0.2 } }
  detector:     { type: yolo_estimator, params: { weight_path: ".../best.pt", verbose: false } }
  postprocess:  { type: transform_result, params: { classes: "U7", not_good_classes: [missing] } }
  output:       { type: merge_result }
edges:
  data: [ preprocess, postprocess ]
  preprocess: detector
  detector: postprocess
  postprocess: output
```

Edges values may be either a single string OR a list of strings (verified in `templates/presets/missing_yolo.yaml` line 32-39).

## 3. Node type registry — full list (49 types)

Authoritative source: `auto-inspect-service/src/auto_inspect_service/schemas/node_params.yaml`.

| Category | Node types |
|---|---|
| **Structural** | `input`, `graph` (subgraph ref), `script`, `switch`, `rejected` |
| **Anomaly** | `anomaly_predictor`, `anomaly_dino_predictor`, `anomaly_imgproc_predictor`, `anomaly_decision`, `anomaly_result` |
| **YOLO family** | `yolo_estimator`, `yolo_anomaly_predictor`, `yolo_crop`, `yolo_fiducial_detector`, `yolo_lifted_pin_detector` |
| **Fiducial / alignment** | `fiducial_detector`, `fiducial_detector_v2`, `orb_alignment_detector`, `circle_alignment_detector`, `threshold_fiducial_detector`, `border_alignment_detector` |
| **Detectors** | `template_match_detector`, `template_match_classifier`, `golden_reference`, `orientation_classifier`, `threshold_detector`, `bright_region_detector`, `bright_region_crop`, `bright_region_split`, `light_background_detector`, `lifted_pin_detector` |
| **Cropping** | `tile_crop`, `threshold_crop` |
| **OCR / barcode** | `ocr_model`, `data_matrix_detector`, `barcode_detector` |
| **Transforms** | `transform_result`, `transform_anomaly_result`, `transform_box_result`, `transform_probs_result`, `transform_single_result`, `transform_ocr_result`, `transform_barcode_result`, `transform_data_matrix_result`, `transform_light_background_result` |
| **Merge / output / debug** | `merge_result`, `merge_tile_result`, `check_missing`, `static_box`, `show_image`, `save_image` |

**MI-defect-specific detectors confirmed present** (matches plan §1.5 claim):
- `lifted_pin_detector` + `yolo_lifted_pin_detector` — wave-solder lifted pin
- `border_alignment_detector` — misalignment of through-hole part
- `orientation_classifier` — electrolytic cap polarity flip, switch direction
- `template_match_classifier` (with `not_good_classes: [missing]`) — missing component

Per-node-type parameter schema (UI metadata: control type, defaults, ranges, choices) is in the same `node_params.yaml` file. The M4 planner should consult this file to generate valid `params` blocks.

## 4. Sibling files in the model directory

### `locations.yaml`

Defines the inspection frames. Camera moves between frames; each frame has a position and which side/region of the PCB it covers. Authoritative example shape per `cli/commands/eval.py` line 500-513:

```yaml
frames:
  - frame_id: "TOP-01"
    side: "top"
    location: { x: 100, y: 50 }
    unit: "mm"
  - frame_id: "TOP-02"
    side: "top"
    location: { x: 200, y: 50 }
    unit: "mm"
  - frame_id: "BOT-01"
    side: "bottom"
    location: { x: 100, y: 50 }
    unit: "mm"
```

The inference endpoint (`POST /api/models/{model_id}/infer`) takes `frame_id` as multipart field and resolves the spatial context from this file (auto-inspect-service `README.md` line 147).

### `settings.yaml`

Camera / lighting config (luminance, gain, exposure, white balance). Schema not enumerated in this spike — defer detailed inspection to M7 (training integration) or M11 (edge orchestration) when we actually need to write it. For v1 of visual-editor, we'll likely PROVIDE a default `settings.yaml` per project and surface only the high-value knobs in the UI.

### `components/*.yaml`

Per-component subgraphs as described in §2 above. One file per BOM-derived component group OR per individual designator (depends on how the planner partitions). M4 design decision.

### `assets/`

Static binaries: fiducial template images, golden reference images, ROI masks. Paths from `params.path` in nodes resolve relative to `config.yaml` parent. M4 planner emits these references; M7 training writes the actual files alongside.

## 5. Templating convention (upstream presets — informational)

The library at `templates/presets/*.yaml` contains 14 reusable pipeline patterns (full_inspection, anomaly_with_orientation, missing_yolo, label_ocr, pin_array, ...). These are **Jinja2 templates** — they contain `{{var|default}}` substitution markers and are NOT directly parseable as YAML. They're rendered by the service's CLI / setup endpoints into the final `config.yaml` shape.

Header comment convention in each preset:
```
# <Title>
# <One-line description>
# Category: <missing|anomaly|composite|ocr|...>
# Params: <param1>, <param2>, ...
nodes:
  ...
```

**Our M4 planner does NOT have to use Jinja**. It can emit fully-rendered YAML directly. The presets are a reference taxonomy of WHICH node compositions are known-good — useful as few-shot examples in the Gemma prompt.

## 6. Open questions (carried into M4)

1. **Which subset of the 49 node types should the Gemma planner emit?** Recommendation: lock the v1 vocabulary to a minimal set sufficient for MI defect coverage + SMT second-check. Proposal:
   - Structural: `input`, `graph`, `merge_result`
   - Crop: `yolo_crop`
   - Detect (per defect criterion mapping in plan §2.2c):
     - `missing_component` → `yolo_estimator` OR `template_match_classifier`
     - `orientation` / `polarity_flip` → `orientation_classifier` + `yolo_estimator`
     - `lifted_pin` → `lifted_pin_detector` OR `yolo_lifted_pin_detector`
     - `misalignment` → `border_alignment_detector`
     - `wrong_value` → `yolo_estimator` + `ocr_model`
     - `solder_short` (whole-side only) → `anomaly_dino_predictor` OR `threshold_detector`
   - Alignment: `fiducial_detector` (top-level)
   - Transforms: `transform_result`, `transform_anomaly_result`, `transform_ocr_result`
   This list lands in `data/defect_detector_mapping.yaml` at Phase 2.2c.
2. **Subgraph granularity** — one subgraph per designator vs per component-group vs per defect-criterion? Plan §2.2 default smart-select is per-designator → likely one subgraph per designator selected for inspection.
3. **Where does the planner write the rendered files?** Two options: (a) directly write to `auto-inspect-service`'s `<models_dir>/<pcb_name>/` via shared filesystem, (b) POST a payload to a new `auto-inspect-service` REST endpoint that writes server-side. Plan §10 question 2 (REST vs subprocess). Decide in M4.
4. **`settings.yaml` defaults** — what's the safe baseline for camera params we ship per new project? Likely copied from a known-good existing PCB's settings + surfaced only the LED brightness knob in UI v1.
5. **Auto-inspect-service Jinja templating** — does the existing setup REST endpoint accept rendered YAML, or does it expect Jinja templates that it renders server-side? Verify in M4 before finalizing planner output format.

## 7. What this spike proved

- The top-level config IS `{name, nodes, edges}` (plan §0.2's assumption was correct, contrary to the snapshot in `templates/presets/` which only shows subgraphs)
- 49 node types are registered; the MI defect detectors the plan claims exist (`lifted_pin_detector`, `border_alignment_detector`, `orientation_classifier`) ARE all present and parameterized
- The schema is loadable with stdlib `yaml.safe_load` once Jinja substitution is done — no custom parser needed
- Two tests in `tests/spike/test_graphflow_schema.py` enforce the structural invariants (top-level has `name`, subgraph doesn't; all node types must be in the known registry; all edge endpoints must be declared nodes)
- M4 planner adapter has a concrete target shape to emit

## 8. Cross-references

- `auto-inspect-service/README.md` §2 — model layout authoritative
- `auto-inspect-service/CLAUDE.md` — internal architecture
- `auto-inspect-service/src/auto_inspect_service/schemas/node_params.yaml` — full per-type UI metadata
- `auto-inspect-service/src/auto_inspect_service/templates/presets/` — 14 preset patterns
- Our plan §M4 (roadmap) — where the planner adapter will use this
- Our plan §2.2c — defect-criterion → detector mapping that feeds the planner
