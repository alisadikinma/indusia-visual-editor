# Label Studio Adoption Strategy — Indusia Visual Editor

> **Status: ACTIVE (v1 execution reference)** — referenced by plan decision #1, §A.1, M6
> Companion to [`docs/plans/2026-05-22-visual-editor-mvp.md`](../plans/2026-05-22-visual-editor-mvp.md)
> Date: 2026-05-22
> Source codebase inspected: `D:\Projects\label-studio` (branch `develop`)

---

## TL;DR — Revision to Phase 1 decision

**Original lock (brainstorm Phase 1):** "Custom labeling UI + Label Studio JSON format only" — build canvas from scratch in Vue/Konva, only adopt the JSON shape.

**Revised recommendation after inspecting the codebase:** **Embed Label Studio Frontend (LSF) library directly as a React island inside our Vue app.** Reasons:

1. LSF is **Apache-2.0**, shipped as a standalone class `window.LabelStudio` instantiable on any DOM node — designed for embedding.
2. LSF already uses **Konva** (same library we were going to use), plus MobX-state-tree state management, undo/redo, multi-region history, hotkeys, zoom/pan/rotate, layers, RLE brush masks, polygon, keypoint, ellipse, bbox-with-rotation, OBB-via-rotation.
3. LSF accepts a declarative **labeling config (XML)** — we can compose per-PCB configs programmatically from BOM + planner output without forking LSF.
4. LSF natively emits **Label Studio JSON format** — zero adapter code.
5. The **ML Backend SDK** is a public HTTP protocol — Gemma 4 implementing this protocol means LSF calls `predict()` automatically; we don't write our own pre-label endpoint plumbing.
6. Building all of the above from scratch on Konva = ~3–4 weeks of UI work we don't need to do.

**Cost of adoption:** small React-in-Vue wrapper component + dependency on LSF as an npm package or built artifact. Acceptable trade-off.

What we still build ourselves: dashboard, project wizard, BOM parser, training/eval/deploy screens, chat advisor, Gemma orchestration. Only the labeling canvas itself comes from LSF.

---

## 1. What LSF actually is (anchored to source code)

### 1.1 Repo layout (relevant parts)

```
D:\Projects\label-studio\
├── web\                       ← Yarn + NX monorepo, JS/TS frontend
│   ├── apps\labelstudio\      Main SPA (Django serves it)
│   ├── libs\
│   │   ├── editor\            ← LSF — Label Studio Frontend (what we adopt)
│   │   │   ├── src\
│   │   │   │   ├── index.js            window.LabelStudio = LabelStudio
│   │   │   │   ├── LabelStudio.tsx     class LabelStudio (root, options)
│   │   │   │   ├── Component.jsx       React component variant
│   │   │   │   ├── defaultOptions.js   interfaces array (panel/submit/skip/…)
│   │   │   │   ├── configureStore.js   MobX-state-tree setup
│   │   │   │   ├── tags\               XML tag implementations
│   │   │   │   │   ├── object\Image\   <Image> tag
│   │   │   │   │   └── control\        <RectangleLabels>, <PolygonLabels>, …
│   │   │   │   ├── regions\            region models (RectRegion, PolygonRegion, …)
│   │   │   │   └── examples\image_bbox\ reference config.xml + tasks.json
│   │   │   └── package.json     deps: react 18, konva 8, mobx-state-tree 3, …
│   │   ├── datamanager\        (we DO NOT adopt — replaced by our own dashboard)
│   │   ├── core\               shared utils
│   │   └── ui\                 design system (we DO NOT adopt — our own brand)
│   └── package.json            workspace root, scripts: lsf:watch, lsf:serve, …
└── label_studio\               ← Django backend (we DO NOT adopt — our FastAPI replaces it)
    ├── ml\                     ML backend HTTP protocol spec
    └── ...
```

### 1.2 Embedding entry point (verified at `web/libs/editor/src/LabelStudio.tsx`)

```ts
// LSF expects a DOM node + options
const instance = new LabelStudio(rootDiv, {
  config: '<View>...</View>',       // labeling config XML
  task: {
    id: 1,
    data: { image: 'https://.../golden_top.jpg' },
    annotations: [],
    predictions: [{ model_version: 'gemma-prelabel-v1', result: [...] }],
  },
  interfaces: [                       // controls which UI chrome to show
    'panel', 'controls', 'side-column',
    'submit', 'update', 'skip',
    'annotations:history', 'annotations:menu',
    'predictions:tabs', 'auto-annotation', 'edit-history',
  ],
  user: { pk: 1, firstName: 'Operator', lastName: 'Indusia' },
  onSubmitAnnotation: (ls, annotation) => { /* save to our backend */ },
  onUpdateAnnotation: (ls, annotation) => { /* save to our backend */ },
  onSkipTask: (ls) => { /* … */ },
  onTaskLoad: (ls, task) => { /* … */ },
  instanceOptions: { reactVersion: 'v18' },  // important — match our React 18
});

// destroy when unmounting
instance.destroy();
```

The class manages its own React root (`createRoot(rootElement)` for v18, `render()` for v17) and MobX store. It exposes `window.Htx` as a global store handle for debugging.

### 1.3 Output format (LS-JSON — verified at `examples/image_bbox/annotations/1.json`)

```jsonc
{
  "annotations": [
    {
      "id": "1001",
      "lead_time": 15.053,
      "result": [
        {
          "from_name": "tag",               // matches <RectangleLabels name="tag">
          "to_name": "img",                 // matches <Image name="img">
          "id": "Dx_aB91ISN",
          "source": "$image",
          "type": "rectanglelabels",
          "value": {
            "x": 50.8, "y": 5.87,           // percentages of image dims
            "width": 12.4, "height": 10.46,
            "rotation": 0,
            "rectanglelabels": ["Moonwalker"]
          }
        }
      ]
    }
  ],
  "predictions": [ /* same shape, model_version + score */ ],
  "data": { "image": "https://..." },
  "id": 1
}
```

Coordinates **always normalized to image dimensions (percentages, not pixels)**. This is important for our pipeline because PCB images at the inspection rig will be a fixed resolution — we can convert to absolute pixels deterministically when feeding into the auto-inspect-service training data.

### 1.4 Labeling config (XML, verified at `examples/image_bbox/config.xml`)

```xml
<View>
  <Image name="img" value="$image"/>
  <RectangleLabels name="tag" toName="img" fillOpacity="0.5" strokeWidth="5">
    <Label value="Planet"/>
    <Label value="Moonwalker" background="blue"/>
  </RectangleLabels>
</View>
```

This is the labeling schema. We generate it dynamically per PCB:

- `<Image>` → golden sample
- `<RectangleLabels>` → one `<Label>` per BOM designator (R1, C4, U7, …) auto-populated
- For polygonal / OBB needs (fiducial mark with rotation): add `<PolygonLabels>` or use `rotation` attribute on RectangleLabels
- For brush mask (anomaly defect region) on per-component crops: add `<BrushLabels>`
- For per-region attributes (e.g., orientation tag, OCR transcription): add `<Choices perRegion="true">` or `<TextArea perRegion="true">`

### 1.5 ML Backend protocol (HTTP)

LSF expects the backend to be a separate HTTP service speaking this contract:

```
POST /predict
Request body:
  {
    "tasks": [ { "data": { "image": "..." }, ... } ],
    "context": { "annotation_id": ..., "draft_id": ..., "result": [...] },
    "params": { ... }
  }
Response:
  {
    "results": [
      { "result": [<LS-JSON result items>], "score": 0.87, "model_version": "..." }
    ]
  }

POST /setup       (called when LSF connects)
POST /webhook     (annotation created/updated events for fit())
GET  /health
```

Spec reference: `D:\Projects\label-studio\label_studio\ml\README.md` + the `LabelStudioMLBase` class in `label-studio-ml-backend` repo.

**This is the integration seam for Gemma 4.** We expose Gemma's pre-label and judge endpoints behind this protocol → LSF treats Gemma as a regular ML backend. Native UX: when user clicks "Get predictions" in LSF, it auto-calls our wrapper → Gemma → returns predictions → user reviews/corrects → submit → save to our DB.

---

## 2. Adoption mode for Indusia Visual Editor

```
┌──────────────────────────────────────────────────────────────────┐
│ Vue 3 SPA (our app)                                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Dashboard.vue  │  Wizard.vue  │  TrainEval.vue  │  Deploy  │  │
│  ├────────────────────────────────────────────────────────────┤  │
│  │ LabelingCanvas.vue                                          │  │
│  │  └─ <LSFEmbed config={xml} task={task} on-submit={save} /> │  │
│  │      └─ <div ref="lsfRoot" />                              │  │
│  │          └─ new LabelStudio(lsfRoot, { …Vue-bridged… })   │  │ ← React island
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┬─┘
                                                                 │
                                                                 ▼
                              ┌──────────────────────────────────────────┐
                              │ indusia-visual-editor backend (FastAPI)  │
                              │                                          │
                              │ /api/labels/lsf-tasks/{project_id}       │← serves task JSON
                              │ /api/labels/submit                        │← receives annotations
                              │ /api/ml-backend/predict       (LSF spec)  │← Gemma pre-label
                              │ /api/ml-backend/setup                     │
                              │ /api/ml-backend/webhook                   │
                              │ /api/ml-backend/health                    │
                              └──────────────────────────────────────────┘
                                                                 │
                                                                 ▼
                                                       ┌─────────────────┐
                                                       │ Ollama gemma4   │
                                                       │ :31b (HTTP)     │
                                                       └─────────────────┘
```

### 2.1 LSF as a React island inside Vue 3

LSF is React 18. Vue 3 hosts it via a tiny wrapper. Recipe:

`web/src/components/LSFEmbed.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';

const props = defineProps<{
  config: string;          // labeling config XML
  task: object;            // task JSON (data + predictions)
  interfaces?: string[];
}>();

const emit = defineEmits<{
  (e: 'submit', annotation: any): void;
  (e: 'update', annotation: any): void;
  (e: 'skip'): void;
}>();

const lsfRoot = ref<HTMLDivElement | null>(null);
let lsfInstance: any = null;

const mount = async () => {
  if (!lsfRoot.value) return;
  // LabelStudio is exposed on window after the lsf bundle is loaded
  const LabelStudio = (window as any).LabelStudio
    ?? (await import('@humansignal/editor')).LabelStudio;

  lsfInstance = new LabelStudio(lsfRoot.value, {
    config: props.config,
    task: props.task,
    interfaces: props.interfaces ?? [
      'panel', 'controls', 'side-column',
      'submit', 'update', 'skip',
      'annotations:history', 'annotations:menu', 'predictions:tabs',
      'auto-annotation', 'edit-history',
    ],
    instanceOptions: { reactVersion: 'v18' },
    onSubmitAnnotation: (_ls: any, ann: any) => emit('submit', ann),
    onUpdateAnnotation: (_ls: any, ann: any) => emit('update', ann),
    onSkipTask: () => emit('skip'),
  });
};

const reload = () => {
  lsfInstance?.destroy?.();
  lsfInstance = null;
  mount();
};

onMounted(mount);
onBeforeUnmount(() => lsfInstance?.destroy?.());

// Re-mount whenever config or task changes (LSF doesn't hot-reload config)
watch(() => [props.config, props.task], reload, { deep: false });
</script>

<template>
  <div ref="lsfRoot" class="lsf-host" />
</template>

<style scoped>
.lsf-host { width: 100%; height: calc(100vh - 64px); }
</style>
```

Parent usage:

```vue
<LSFEmbed
  :config="labelingConfigXml"
  :task="lsfTask"
  @submit="onAnnotationSubmit"
  @update="onAnnotationUpdate"
/>
```

### 2.2 Two viable distribution options

**Option (a) — npm package via the upstream repo's build artifact (RECOMMENDED v1)**

LSF is in a private workspace; not published to public npm. Steps to consume — **verified end-to-end in [`lsf-build.md`](./lsf-build.md) on 2026-05-22**:

1. Clone Label Studio repo as a sibling: `D:\Projects\label-studio\` (already there)
2. Prep yarn 1.22.22 via corepack (do NOT use yarn 4 — lockfile is v1):
   ```powershell
   corepack prepare yarn@1.22.22
   ```
3. In `D:\Projects\label-studio\web\`, install deps (~10 min cold, 746 MB node_modules):
   ```powershell
   corepack yarn@1.22.22 install --frozen-lockfile --network-timeout 600000
   ```
4. Build the LSF library bundle (~4 min). The `MODE=standalone` env var is **required** — without it webpack builds the labelstudio SPA instead of the editor library:
   ```powershell
   $env:MODE="standalone"; $env:NODE_ENV="production"
   corepack yarn@1.22.22 nx run editor:build:production
   ```
5. Output lands at `D:\Projects\label-studio\web\dist\libs\editor\` (NOT `web/libs/editor/dist/`). Contents: `main.js` (4.5 MB ES module), `main.css` (1.5 MB), 5 async chunks (`29.js`, `131.js`, `352.js`, `616.js`, `710.js`), `decode-audio.wasm`, `Figtree-*.ttf`, `3rdpartylicenses.txt`, and a demo `public/` dir.
6. Vendor the ENTIRE built tree (minus `*.map` and demo `public/files/`) into our app's `web/public/lsf/`. Webpack runtime loads the async chunks by relative path — shipping only `main.js` + `main.css` will fail at runtime:
   ```powershell
   robocopy D:\Projects\label-studio\web\dist\libs\editor `
            D:\Projects\indusia-visual-editor\web\public\lsf `
            /MIR /XF "*.map" /XD "public\files"
   ```
7. Load via `<script type="module" src="/lsf/main.js"></script>` in `web/index.html`. Webpack 5 emits ES-module output; `type="module"` is required. After load, `window.LabelStudio` is a constructable class.

Lightweight, no monorepo mess. Re-build only when upgrading LSF. Apache 2.0 obligation: keep `3rdpartylicenses.txt` next to the bundle and add HumanSignal attribution to our app's About page.

**Option (b) — Vendor LSF source into our monorepo (deferred to v2 if we need to customize)**

If we ever want to fork LSF (e.g., add Indusia branding, hide certain features, custom region types), copy `web/libs/editor` into our repo as a workspace package. Heavier maintenance — defer until pain justifies it.

### 2.3 Licensing implications

LSF is **Apache 2.0** (`web/libs/editor` license headers + root `LICENSE`). Commercial use OK. Requirements: preserve license notice + attribution in our distribution. Standard Apache attribution boilerplate in `web/public/lsf/LICENSE.txt`. No further obligations — we can ship Indusia Visual Editor as a commercial / closed product.

---

## 3. PCB-specific labeling config (auto-generated per project)

Generated by `services/llm/planner.py` + `services/label/config_builder.py` after BOM upload + Gemma plan.

### 3.1 Example output for a simple PCB

```xml
<View>
  <Header value="PCB: NV7320H-1 — TOP side"/>
  <Image name="img" value="$image" zoom="true" zoomControl="true" rotateControl="false"/>

  <RectangleLabels name="component" toName="img"
                   fillOpacity="0.3" strokeWidth="2"
                   allowEmpty="false">
    <Label value="R1"  background="#ff6b6b"/>
    <Label value="R2"  background="#ff6b6b"/>
    <Label value="C4"  background="#4ecdc4"/>
    <Label value="U7"  background="#ffd93d"/>
    <Label value="U8"  background="#ffd93d"/>
    <Label value="W1"  background="#a78bfa"/>
    <!-- … one <Label> per BOM designator … -->
  </RectangleLabels>

  <!-- Per-region attributes: orientation (for polarized parts), OCR (for ICs) -->
  <Choices name="orientation" toName="img" perRegion="true"
           visibleWhen="region-selected" whenLabelValue="C4,C5,C6"
           showInLine="true">
    <Choice value="correct" hotkey="o"/>
    <Choice value="flipped" hotkey="f"/>
  </Choices>

  <TextArea name="ocr_value" toName="img" perRegion="true"
            visibleWhen="region-selected" whenLabelValue="U7,U8"
            placeholder="Read IC marking" maxSubmissions="1" rows="1"/>

  <!-- Fiducial marks (key for alignment in inspection) -->
  <KeyPointLabels name="fiducial" toName="img" strokeWidth="3">
    <Label value="fiducial_TL" background="#00ff00"/>
    <Label value="fiducial_TR" background="#00ff00"/>
    <Label value="fiducial_BL" background="#00ff00"/>
  </KeyPointLabels>

  <!-- For defect labeling on golden vs sample comparison flows (v1.5+) -->
  <BrushLabels name="defect" toName="img" choice="single">
    <Label value="solder_bridge"  background="#ef4444"/>
    <Label value="missing_part"   background="#f59e0b"/>
    <Label value="misalignment"   background="#8b5cf6"/>
  </BrushLabels>
</View>
```

Notes on choices:

- **`RectangleLabels` not `Rectangle`** — embeds the class label in the bbox (matches the YOLO detector training signal we want).
- **`KeyPointLabels` for fiducials** — fiducial center is a single point, fits the `FiducialDetector` in `auto-inspect-engine`.
- **`Choices perRegion` for orientation** — captures polar-cap flip state which inspection engine needs (matches existing `auto-inspect-engine` post-processing).
- **`TextArea perRegion` for IC markings** — labels become OCR ground truth for the engine's `OcrModel`.
- **`BrushLabels` for defect mask** — RLE-compressed mask, the engine has `label_studio_converter.brush` helper to convert (also our planner doc mentions Anomalib needs binary masks during anomaly training; this is the path).

### 3.2 Generation in code

`services/label/config_builder.py`:

```python
from jinja2 import Template

LSF_CONFIG_TEMPLATE = Template("""<View>
  <Header value="{{ project_name }} — {{ side|upper }} side"/>
  <Image name="img" value="$image" zoom="true" zoomControl="true"/>

  <RectangleLabels name="component" toName="img" fillOpacity="0.3" strokeWidth="2" allowEmpty="false">
  {% for item in bom_items %}
    <Label value="{{ item.designator }}" background="{{ color_for(item.component_type) }}"/>
  {% endfor %}
  </RectangleLabels>

  {% if has_polarized %}
  <Choices name="orientation" toName="img" perRegion="true" visibleWhen="region-selected"
           whenLabelValue="{{ polarized_designators|join(',') }}" showInLine="true">
    <Choice value="correct" hotkey="o"/>
    <Choice value="flipped" hotkey="f"/>
  </Choices>
  {% endif %}

  {% if has_ocr %}
  <TextArea name="ocr_value" toName="img" perRegion="true" visibleWhen="region-selected"
            whenLabelValue="{{ ocr_designators|join(',') }}"
            placeholder="Read IC marking" maxSubmissions="1" rows="1"/>
  {% endif %}

  <KeyPointLabels name="fiducial" toName="img" strokeWidth="3">
    {% for f in fiducials %}<Label value="{{ f.name }}" background="#00ff00"/>{% endfor %}
  </KeyPointLabels>
</View>""")


def build_lsf_config(project: Project, side: str) -> str:
    return LSF_CONFIG_TEMPLATE.render(
        project_name=project.name, side=side,
        bom_items=project.bom_items,
        has_polarized=any(i.is_polarized for i in project.bom_items),
        polarized_designators=[i.designator for i in project.bom_items if i.is_polarized],
        has_ocr=any(i.needs_ocr for i in project.bom_items),
        ocr_designators=[i.designator for i in project.bom_items if i.needs_ocr],
        fiducials=project.fiducials,
        color_for=color_for_component_type,
    )
```

The Gemma planner output (`ProposedPipelineStep.detectors`) determines `is_polarized` / `needs_ocr` flags per BOM item.

---

## 4. Gemma 4 as an LSF ML Backend

Best fit: serve Gemma behind the LSF ML backend protocol so the labeling UI's native "Predict" button just works.

### 4.1 Backend route layout (`routes/ml_backend.py`)

```python
from fastapi import APIRouter, HTTPException
from .schemas import MLPredictRequest, MLPredictResponse

router = APIRouter(prefix="/api/ml-backend")


@router.get("/health")
async def health():
    return {"status": "UP", "model_version": "gemma-prelabel-v1"}


@router.post("/setup")
async def setup(req: dict):
    # LSF sends labeling config + project info on connect.
    # Cache config per project so /predict can render the right prompt.
    return {"model_version": "gemma-prelabel-v1"}


@router.post("/predict", response_model=MLPredictResponse)
async def predict(req: MLPredictRequest):
    # tasks = [{ data: { image: "..." }, ... }]
    # For each task: download/read image, render BOM context, call Gemma, parse output → LS-JSON.
    results = []
    for task in req.tasks:
        image_url = task["data"]["image"]
        image_bytes = await load_image_bytes(image_url)
        project_id = task.get("meta", {}).get("project_id")  # we inject this when serving task
        bom = await get_bom(project_id)

        prelabel = await llm.prelabel.predict(image_bytes, bom)
        # prelabel is list[PreLabeledRegion]; convert to LS-JSON
        ls_result = [
            {
                "from_name": "component",
                "to_name": "img",
                "type": "rectanglelabels",
                "id": str(uuid4()),
                "value": {
                    "x": r.bbox[0] * 100, "y": r.bbox[1] * 100,
                    "width": r.bbox[2] * 100, "height": r.bbox[3] * 100,
                    "rotation": 0,
                    "rectanglelabels": [r.designator],
                },
                "score": r.confidence,
            }
            for r in prelabel
        ]
        results.append({"result": ls_result, "score": mean_conf(prelabel), "model_version": "gemma-prelabel-v1"})

    return {"results": results}


@router.post("/webhook")
async def webhook(event: dict):
    # LSF sends annotation events here when fit() is enabled.
    # For v1 we ignore (no online training). Log for observability.
    logger.info("LSF webhook event", extra={"event_type": event.get("action")})
    return {"status": "ok"}
```

### 4.2 Connecting LSF to our ML backend

LSF doesn't auto-discover ML backends; it has to be told. Two ways:

**(a)** Through the labeling config: add `<View>` attributes (not standard — skip)
**(b)** Through the instance options: pass `ml_backend_url` via `options` when constructing LSF (verify LSF supports this — fallback: send predictions inline with the task JSON)

**Pragmatic v1:** Skip live "Predict" button calls and just **bake predictions into the task JSON we serve to LSF**. Flow:

```
1. User opens LabelingCanvas.vue for project X side TOP
2. Frontend calls GET /api/labels/lsf-tasks/{project_id}?side=top
3. Backend:
     a. fetch golden_top asset
     b. call llm.prelabel.predict(golden_top, bom) → list[PreLabeledRegion]
     c. assemble task JSON with predictions[] populated
     d. return task + config XML
4. Frontend mounts <LSFEmbed :config :task />
5. LSF renders predictions as proposed regions (orange ring) — user can promote
   to annotation with one click (existing LSF feature)
```

This skips the ML backend protocol entirely for v1 — simpler, fewer moving parts, same end-user UX. Promote to true ML-backend mode in v1.5 when we want interactive "click magic wand to detect this region" features (Segment Anything-style).

---

## 5. Backend storage of LS-JSON

Our `labels` table from the plan stores LS-format JSON natively. Key fields when annotation arrives via `onSubmitAnnotation`:

```python
class LabelService:
    async def submit_annotation(
        self, project_id: UUID, side: Literal["top", "bottom"],
        annotation: dict, user_id: UUID,
    ) -> Label:
        # annotation is the LSF onSubmit payload — exactly LS-JSON shape:
        #   { id, lead_time, result: [...], created_at?, completed_by? }
        validated = LSAnnotation.model_validate(annotation)
        snapshot = await self._next_version(project_id, side)
        row = Label(
            project_id=project_id, side=side, version=snapshot,
            ls_json=validated.model_dump(),
            user_id=user_id,
        )
        # Optional: also write a filesystem snapshot for git-style diff/restore
        await self._snapshot_to_fs(row)
        return await self.repo.create(row)
```

LS-JSON validators (extracted directly from LSF examples — `web/libs/editor/src/examples/image_bbox/annotations/1.json`):

```python
class LSResultValue(BaseModel):
    x: float; y: float; width: float; height: float; rotation: float = 0
    rectanglelabels: list[str] | None = None
    polygonlabels: list[str] | None = None
    keypointlabels: list[str] | None = None
    brushlabels: list[str] | None = None
    choices: list[str] | None = None
    text: list[str] | None = None
    points: list[list[float]] | None = None   # polygon
    rle: list[int] | None = None              # brush
    radiusX: float | None = None
    radiusY: float | None = None

class LSResult(BaseModel):
    id: str
    from_name: str
    to_name: str
    type: Literal["rectanglelabels", "polygonlabels", "keypointlabels",
                  "brushlabels", "choices", "textarea", "rectangle",
                  "polygon", "ellipse", "keypoint"]
    value: LSResultValue
    source: str | None = None
    origin: str | None = None     # "manual" | "prediction" | "prediction-changed"
    original_width: int | None = None
    original_height: int | None = None
    image_rotation: float | None = None

class LSAnnotation(BaseModel):
    id: str | int
    lead_time: float | None = None
    result: list[LSResult]
    completed_by: int | None = None
    was_cancelled: bool = False
```

### 5.1 LS-JSON → engine training format adapter

The auto-inspect-engine consumes YOLO-style `.txt` label files (class_id x_center y_center w h, all normalized). Adapter in `services/label/exporter.py`:

```python
def ls_to_yolo(annotation: LSAnnotation, class_index: dict[str, int]) -> str:
    lines = []
    for r in annotation.result:
        if r.type != "rectanglelabels":
            continue
        v = r.value
        cls = class_index[v.rectanglelabels[0]]
        # LS-JSON x/y/w/h are TOP-LEFT-anchored percentages.
        # YOLO wants center-anchored, normalized 0-1.
        x_c = (v.x + v.width / 2) / 100
        y_c = (v.y + v.height / 2) / 100
        w = v.width / 100
        h = v.height / 100
        lines.append(f"{cls} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}")
    return "\n".join(lines)
```

Polygon and brush exports go through `label-studio-converter` (pip package — Apache 2.0) for RLE → mask conversion.

---

## 6. Updates to the implementation plan

The brainstorm + plan doc at [`docs/plans/2026-05-22-visual-editor-mvp.md`](../plans/2026-05-22-visual-editor-mvp.md) needs targeted updates. Concretely:

### 6.1 Decisions to update (under "Locked decisions" section)

| # | Old | New |
|---|---|---|
| 1 | Custom Vue 3 + Konva canvas, output LS JSON | **Embed LSF (Apache-2.0 React library) as React island in Vue; LS-JSON native** |

### 6.2 Stack additions

Add to "Tech Stack" table:
- `@humansignal/editor` (LSF bundle, Apache 2.0) — built from `D:\Projects\label-studio` and vendored under `web/public/lsf/` or `web/vendor/lsf/`
- `label-studio-converter` (Python, Apache 2.0) for brush RLE ↔ mask + LS-JSON ↔ YOLO/COCO exports
- React 18 + ReactDOM as peer deps for the LSF island (no other React in our app — single isolated island)

### 6.3 M6 milestone simplification

Original M6 ("Labeling canvas (Konva + LS-JSON)") at 4 days reduces to ~2 days because canvas + tools + history come from LSF. New M6 phase breakdown:

- **6.1** Build LSF bundle from `D:\Projects\label-studio` (or pin a tag), vendor `dist/main.js` + `main.css` into `web/public/lsf/` — 30 min
- **6.2** Implement `LSFEmbed.vue` wrapper with config + task props + submit/update/skip events — 1.5 h
- **6.3** Implement `services/label/config_builder.py` (Jinja templates per PCB) — 2 h
- **6.4** Implement `routes/labels.py` GET `/api/labels/lsf-tasks/{project_id}?side=…` returning `{ config, task }` payload — 1 h
- **6.5** Implement `services/label/ls_format.py` pydantic validators (from §5 above) — 1 h
- **6.6** Implement `routes/labels.py` POST `/api/labels/submit` + DB persistence + versioning — 2 h
- **6.7** Wire `LabelingCanvas.vue` view (top + bottom side toggle, save state) — 2 h
- **6.8** Implement LS-JSON → YOLO `.txt` exporter for training feed — 1.5 h
- **6.9** Smoke test: full label cycle on a real PCB image, verify saved JSON, verify YOLO export — 1 h

### 6.4 M5 milestone simplification

Original M5 ("Pre-label assistant") at 2 days holds, but the integration target shifts. Two variants:

- **5a (v1):** Pre-label predictions baked into task JSON served by `/api/labels/lsf-tasks/...` (as in §4.2 above). Simple, no LSF↔backend live calls.
- **5b (v1.5):** Implement LSF ML backend protocol (`/api/ml-backend/predict` + setup + webhook) — enables LSF native "Predict" button + interactive Segment-Anything-style features.

Plan v1 ships only 5a. 5b is roadmap.

### 6.5 New Data Integration Map row

Add to the map:
- `LSF labeling canvas` | bundled UMD at `web/public/lsf/main.js` | global `window.LabelStudio` | **YES** (vendored from `D:\Projects\label-studio`) | Mount via `LSFEmbed.vue` wrapper

### 6.6 New Phase 0.5 spike (before M6)

Add to M0 (or run alongside M1):
- **0.5** Build LSF locally per the corrected procedure in [`lsf-build.md`](./lsf-build.md) §2: prep yarn 1.22.22 via corepack, `yarn install --frozen-lockfile`, then `MODE=standalone NODE_ENV=production yarn nx run editor:build:production`. Verify `D:\Projects\label-studio\web\dist\libs\editor\main.js` exists (~4.5 MB) and contains the `LabelStudio` identifier. Smoke-test by serving the dist dir via `python -m http.server` and confirming `window.LabelStudio` is a function with zero console errors. Time: ~15 min cold, ~4 min hot. **Status: COMPLETED 2026-05-22** — see `lsf-build.md`.

---

## 7. Risks + mitigation

| Risk | Severity | Mitigation |
|---|---|---|
| LSF bundle size (~3–5 MB) bloats our app | Medium | Load LSF lazily — only on `/projects/:id/label` route via dynamic import. Other routes don't include it. |
| LSF version skew with React peer dep (React 17 vs 18) | Low | Pin `instanceOptions.reactVersion: 'v18'` (verified in `LabelStudio.tsx:94`). Our app is React-free except this island, so no peer conflict. |
| LSF internal API changes between upstream commits | Medium | Pin to a specific upstream tag (`develop` at commit X). Re-bundle deliberately on upgrades. Document chosen commit in `docs/specs/lsf-build.md`. |
| LSF UI branding (Heartex / HumanSignal labels) leaks | Low | LSF interfaces are toggleable; remove `"topbar"`, customize via CSS injection in our wrapper. For deeper branding → Option (b) vendor source. |
| Custom region types (e.g., oriented bbox for non-axis-aligned IC) | Medium | LSF supports `rotation` on `RectangleLabels` (verified in example JSON `rotation: 0` field). For full OBB, polygon is a workaround until upstream rotation tools land. |
| Large PCBs (300+ regions × 2 sides) canvas perf | Medium | LSF uses Konva which is GPU-accelerated; benchmark with 600-region sample in Phase 0.5 spike. If slow, LSF has `<Image zoom="true">` virtualization. |
| License obligation tracking | Low | Add `LICENSE.LSF.txt` + `NOTICE.txt` to web/public/lsf/; cite Apache 2.0 + © HumanSignal in our About page. |

---

## 8. What we do NOT adopt from Label Studio

For clarity, explicitly NOT adopted from `D:\Projects\label-studio\`:

| Module | Reason |
|---|---|
| `label_studio/` (Django backend) | We have our own FastAPI; Django + ours is two backends |
| `web/apps/labelstudio` (SPA) | We have our own Vue 3 app |
| `web/libs/datamanager` | We have our own dashboard/wizard tailored to PCB factory user |
| `web/libs/ui` design system | We have our own Indusia brand tokens |
| Postgres schema, RQ workers, Django ORM | Our schema is project-specific |
| Cloud storage adapters (S3, GCS, Azure) | Out of scope v1; filesystem only |
| User/org/team RBAC | We have basic JWT auth (M13) |
| Webhooks / event bus | Maybe revisit at M11 (edge notification) — our use case is narrower |

This separation keeps the integration surface minimal and the adoption reversible.

---

## 9. References

- LSF README: `D:\Projects\label-studio\web\libs\editor\README.md`
- LSF entry point: `D:\Projects\label-studio\web\libs\editor\src\LabelStudio.tsx`
- Example image bbox config: `D:\Projects\label-studio\web\libs\editor\src\examples\image_bbox\config.xml`
- Example annotation: `D:\Projects\label-studio\web\libs\editor\src\examples\image_bbox\annotations\1.json`
- Predictions guide: `D:\Projects\label-studio\docs\source\guide\predictions.md`
- ML backend docs: `D:\Projects\label-studio\docs\source\guide\ml_create.md`
- RectangleLabels tag: `D:\Projects\label-studio\docs\source\tags\rectanglelabels.md`
- Build commands: `web/README.md` (yarn lsf:watch / yarn lsf:serve / yarn lsf:build)
- ML backend SDK repo (external): https://github.com/HumanSignal/label-studio-ml-backend
- Label Studio converter (external): https://github.com/HumanSignal/label-studio-converter

---

## 10. Next actions

1. **Apply revisions to the main plan doc** — update locked decisions §2, stack §8 of design, M5/M6 phase counts and tasks, add Phase 0.5 LSF-build spike
2. **Run the spike (Phase 0.5)** — build LSF, verify `dist/main.js` works, write `docs/specs/lsf-build.md`
3. **Decide on labeling config richness for v1** — start with minimal (Image + RectangleLabels + KeyPointLabels) and add per-region Choices + TextArea + BrushLabels iteratively. v1 ships the minimal set; planner can output enriched configs at M4+.
