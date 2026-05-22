# Inspection Spec Document — Input Format & Parser

> **STATUS: DEFERRED TO v1.5** — not in v1 scope per plan decision #13.
> v1 derives inspect_scope + defect_criteria from labeling canvas annotations directly (unified UX, decision #12).
> This doc retained as future reference when inspection-form PDF parser feature is greenlit (typically after v1 ships and some customers request import of existing inspection forms).
>
> Companion to [`docs/plans/2026-05-22-visual-editor-mvp.md`](../../plans/2026-05-22-visual-editor-mvp.md) and [`label-studio-adoption.md`](../specs/label-studio-adoption.md)
> Date: 2026-05-22 (last revised)

## TL;DR

MI division engineers already prepare a document called **"Auto Vision Inspection Program Creation Form"** (or similar) per PCB model. This document is the **canonical, authoritative source** for:

1. Which components to inspect (subset of full BOM)
2. What defect types to check per component (missing / orientation / pin-bend / etc.)
3. Side mapping (top vs bottom)
4. Visual location of each inspection zone (annotated on PCB photo)

The visual editor MUST treat this PDF as a **first-class input artifact**, parse it via PyMuPDF + Gemma 4 VLM, and auto-populate the project scope. This replaces 80%+ of manual wizard input.

## Reference document

Real-world example: `PCI Private Limited / NV80-017542-0501 / Novanta Corporation / Top + Bottom / PTH inspection`. PCI = the PCB assembly contractor. Novanta = the brand owner. NV80-017542-0501 = the PCB model. PTH = scope = Plated Through Hole = MI components.

## Document structure (observed)

Each PDF has 1 page per side (top, bottom). Each page contains:

```
┌──────────────────────────────────────────────────────────────┐
│ [Logo]  PCI PRIVATE LIMITED                                  │
│                                                              │
│ AUTO VISION INSPECTION PROGRAM CREATION                      │
│ ─────────────────────────────────────────────                │
│ Project    : ________                  Side : Top            │
│ Customer   : NOVANTA CORPORATION       Model: NV80-…         │
│ Inspection : PTH                                             │
│                                                              │
│ ┌─────┬───────────────────┬─────────────────────────┬──────┐│
│ │ No. │ Location          │ Type of Inspection      │ Side ││
│ ├─────┼───────────────────┼─────────────────────────┼──────┤│
│ │ 1   │ C6, C3            │ Missing Component       │ Top  ││
│ │     │                   │ Orientation             │      ││
│ │ 2   │ P5                │ Missing Component       │ Top  ││
│ │     │                   │ Connector Pin Bending   │      ││
│ │     │                   │ Missing Pin Connector   │      ││
│ │ …   │ …                 │ …                       │ …    ││
│ └─────┴───────────────────┴─────────────────────────┴──────┘│
│                                                              │
│ [Annotated PCB photo with yellow-label boxes per designator] │
│                                                              │
│ Document Owner: Manager             PAGE 2 OF 4              │
└──────────────────────────────────────────────────────────────┘
```

Whole-side inspections (e.g., bottom-side solder short) use a row like:

```
│ 1 │ Bottom Side       │ Solder Short            │ Bottom │
```

## Structured output schema (pydantic)

```python
from typing import Literal
from pydantic import BaseModel

DefectType = Literal[
    "missing_component",
    "orientation",
    "polarity_flip",
    "connector_pin_bending",
    "missing_pin_connector",
    "solder_short",
    "solder_bridge",
    "lifted_pin",
    "wrong_value",          # OCR-based
    "wrong_part",           # YOLO classifier confusion
    "misalignment",
    "scratch_or_damage",    # cosmetic, Anomalib
    "other",
]

class InspectionZone(BaseModel):
    zone_id: int                            # row no in the table
    designators: list[str]                  # ["C6", "C3"] or ["P8", "P3", "P1"]
    defect_types: list[DefectType]
    side: Literal["top", "bottom"]
    scope_mode: Literal["per_component", "whole_side"] = "per_component"
    # Visual annotations from the PCB photo (Gemma extracted)
    bbox_seeds: list[tuple[float, float, float, float]] | None = None
        # Normalized [x, y, w, h] 0-1, one per designator (best-effort)
    polarity_marker: bool = False           # was there a "+" sign near the component?
    notes: str | None = None                # free-form remarks

class InspectionSpec(BaseModel):
    project_name: str
    customer: str
    model_product: str
    inspection_category: str                # "PTH", "SMT post-place", etc.
    document_owner: str
    pages: list[Literal["top", "bottom"]]
    zones: list[InspectionZone]
    raw_pdf_sha256: str
    parser_version: str
    parser_confidence: float                # Gemma self-reported 0-1
    warnings: list[str] = []                # e.g., "Page 2 unreadable, used VLM fallback"
```

## Parser pipeline

```
PDF file
   ↓
[Stage A] PyMuPDF extract: text spans with bbox, embedded images, page metadata
   ↓
[Stage B] Heuristic table parser:
   - Detect 4-column layout (No / Location / Type / Side)
   - Extract rows deterministically when text is selectable
   ↓
[Stage C] Gemma 4 VLM read each page image:
   - Parse header (project/customer/model/side)
   - Parse table (cross-check against Stage B)
   - Identify annotated PCB photo location
   - Detect yellow-label boxes → extract (designator label, bbox in image-relative coords)
   - Detect "+" markers (polarity) and red-dashed zones (special areas)
   ↓
[Stage D] Reconciler:
   - Merge Stage B + C outputs
   - If conflict, prefer text extraction for table cells, VLM for visual annotations
   - Map each table row → designators in BOM (auto-set inspect_scope='inspected')
   - Map defect_types → detector_presets (lookup table below)
   - Compute parser_confidence + warnings
   ↓
InspectionSpec JSON → store in DB + show review UI in wizard
```

## Defect type → detector preset mapping

This becomes the bridge between the inspection form and the graphflow DAG planner.

| `DefectType` | Engine detectors (from `auto-inspect-engine`) | LSF labeling control tags | Notes |
|---|---|---|---|
| `missing_component` | YOLO detect (class=designator); FAIL on absence | `<RectangleLabels>` | Most common; baseline |
| `orientation` | YOLO + per-region `<Choices>` (correct/flipped) | `<Choices perRegion>` | For non-polarized rotational checks |
| `polarity_flip` | Same as orientation + polarity template (`+` mark detection) | `<Choices perRegion>` + `<KeyPointLabels>` for `+` sign | Polarized electrolytic caps, diodes |
| `connector_pin_bending` | Anomalib per-ROI + `lifted_pin` detector | `<BrushLabels>` for pin region anomaly | Existing engine has this |
| `missing_pin_connector` | YOLO fine-grained + count check (expected vs detected pins) + template match | `<KeyPointLabels>` for each pin | Count-based: 8-pin header → must detect 8 |
| `solder_short` | Anomalib (whole-side) + threshold detector for solder-bridge pattern | `<BrushLabels>` whole-side | `scope_mode='whole_side'` |
| `solder_bridge` | Same as solder_short but per-pad ROI | `<BrushLabels>` per pad pair | Finer-grained variant |
| `lifted_pin` | `lifted_pin` detector (engine `models/custom/`) | `<KeyPointLabels>` for pin tip + `<Choices>` for state | MI-specific, wave solder defect |
| `wrong_value` | OCR + string match vs BOM `value` field | `<TextArea perRegion>` for transcription | Resistor color band or IC marking |
| `wrong_part` | YOLO classifier confidence + class-mismatch alert | `<RectangleLabels>` baseline | Detect IC silhouette vs expected class |
| `misalignment` | `border_alignment` detector (existing) + Anomalib | `<RectangleLabels>` with `rotation` field | Manual placement skew |
| `scratch_or_damage` | Anomalib unsupervised | `<BrushLabels>` | Cosmetic |
| `other` | Defaults to Anomalib + flag for human review | Multiple | Catch-all |

Maintained in `data/defect_detector_mapping.yaml` — editable without code change.

## Storage in DB

```sql
inspection_specs
  id UUID PK
  project_id UUID FK → projects
  raw_pdf_asset_id UUID FK → assets (kind='inspection_spec')
  parsed_json JSONB          -- full InspectionSpec
  parser_confidence FLOAT
  parser_warnings TEXT[]
  approved_by UUID NULL      -- user who reviewed the parse
  approved_at TIMESTAMPTZ NULL
  created_at TIMESTAMPTZ
  updated_at TIMESTAMPTZ

inspection_zones           -- denormalized for query
  id UUID PK
  spec_id UUID FK → inspection_specs
  zone_id INT
  side TEXT
  scope_mode TEXT
  designators TEXT[]
  defect_types TEXT[]
  bbox_seeds JSONB           -- list of [x, y, w, h]
  polarity_marker BOOL
  notes TEXT
```

Trigger on `inspection_spec` approval: bulk-update `bom_items.inspect_scope='inspected'` for matched designators + set `bom_items.detector_presets` from defect type mapping.

## Wizard flow update (revised)

```
Step 1: Project init (name, slug)
Step 2: Upload assets
        ├─ BOM List (xlsx/csv)               required
        ├─ Golden Sample top (jpg/png)       required
        ├─ Golden Sample bottom (jpg/png)    if 2-sided
        ├─ PCB Drawing (jpg/png)             optional
        └─ ★ Inspection Spec (pdf)           STRONGLY recommended (auto-fills next step)
Step 3: Review parsed inspection spec
        ├─ If PDF uploaded: show parsed table + photo annotations side-by-side
        │   user click "Approve" or "Edit" per zone
        │   parser_confidence < 0.7 → force review
        └─ If no PDF: fall back to manual component-selector (Phase 2.2c from plan)
Step 4: Review proposed pipeline DAG (Gemma planner output, now seeded from spec)
        click Approve
Step 5: Pre-label triggered automatically → open labeling canvas
        bbox_seeds from spec populate predictions[] in LSF task
```

## Integration with Gemma planner (M4)

Planner prompt receives:
- BOM items where `inspect_scope='inspected'`
- Golden sample image
- (optional) PCB drawing image
- ★ **InspectionSpec.zones** as authoritative scope + detector hints

Effect: planner output `ProposedPipelineStep.detectors` becomes mostly **pre-determined** by `defect_detector_mapping.yaml` lookup, not free-form Gemma reasoning. Gemma's job shrinks to: (a) optional add-ons not in spec (e.g., suggest Anomalib even when spec only says "Missing Component" because golden has cosmetic variation), (b) generate the graphflow node connections + parameters.

Risk reduction — deterministic mapping is auditable, predictable, easier to QA across projects.

## Phase additions to implementation plan

Insert into M2 (BOM + assets milestone) after Phase 2.2c:

### Phase 2.2d: PDF parser foundation (PyMuPDF + page rasterization)

**Estimated time:** 12 min
**Files:** `services/asset/pdf_parser.py`, `tests/services/test_pdf_parser.py`, `tests/fixtures/sample_inspection_spec.pdf`

**Steps:**
1. Write failing test `test_parses_real_inspection_spec_pdf_extracts_text_spans` using a fixture PDF. Expected: `ImportError`.
2. Run, see fail.
3. Add `pymupdf` (a.k.a. `fitz`) to deps.
4. Implement `extract_text_spans(pdf_bytes) -> list[PageText]` returning per-page text spans with bbox coords.
5. Implement `rasterize_pages(pdf_bytes, dpi=200) -> list[bytes]` returning PNG bytes per page.
6. Run tests, confirm pass.
7. Commit: `feat(pdf): PyMuPDF wrapper for text spans + page rasterization`

**Verification:**
- [ ] Text extraction roundtrip works on fixture
- [ ] Rasterized images are readable (sanity check by saving + manual open)
- [ ] Encrypted/locked PDF returns typed `PdfParseError` (not unhandled exception)

### Phase 2.2e: Inspection spec parser (PyMuPDF + Gemma reconciliation)

**Estimated time:** 15 min
**Files:** `services/asset/inspection_spec_parser.py`, `services/llm/prompts/inspection_spec.md`, `tests/services/test_inspection_spec_parser.py`, `data/defect_detector_mapping.yaml`

**Steps:**
1. Write failing tests: `test_parses_form_with_clear_table`, `test_handles_whole_side_zone`, `test_extracts_yellow_label_bboxes_from_picture`, `test_reconciler_prefers_text_for_table_visual_for_bboxes`. Use the real form fixture. Expected: `ImportError`.
2. Run, see fail.
3. Author `prompts/inspection_spec.md` instructing Gemma to return `InspectionSpec` JSON shape.
4. Implement `parse_inspection_spec(pdf_bytes) -> InspectionSpec`:
   - Stage A: PyMuPDF text spans
   - Stage B: heuristic 4-col table parse from spans (cluster by y-coord)
   - Stage C: rasterize pages → Gemma call per page with `format=InspectionSpec.model_json_schema()` (page-scoped subset)
   - Stage D: reconciler merges + computes confidence
5. Implement `data/defect_detector_mapping.yaml` (table from §"Defect type → detector preset mapping" above)
6. Run tests against real Ollama instance; iterate prompt until confidence ≥0.85 on the reference form
7. Commit: `feat(inspection-spec): hybrid PyMuPDF+Gemma parser for MI inspection forms`

**Verification:**
- [ ] On reference NV80-017542-0501 form: 6 top zones + 1 bottom zone correctly extracted
- [ ] Defect types map correctly via lookup
- [ ] BBox seeds populated for ≥4 of 6 top zones (yellow-label boxes detected)
- [ ] `whole_side` mode correctly set for bottom-side solder short
- [ ] Parser confidence and warnings present
- [ ] Bahasa Indonesia error messages where user-facing

### Phase 2.2f: Inspection spec upload route + review UI

**Estimated time:** 15 min
**Files:** `routes/inspection_specs.py`, `web/src/views/InspectionSpecReview.vue`, `web/src/components/SpecZoneTable.vue`, `web/src/components/SpecAnnotatedImage.vue`, tests

**Steps:**
1. Failing tests: POST upload returns spec_id + parsed JSON; PATCH approves individual zones + bulk-updates `bom_items.inspect_scope` and detector presets.
2. Implement backend POST + PATCH + GET endpoints.
3. Implement frontend split view: table left, annotated image right with overlay rectangles (draw `bbox_seeds` on top of `rasterized_page_image`).
4. Approval button cascades: `inspection_specs.approved_at=now()` → trigger DB function/service that updates linked BOM items + writes initial `proposed_pipelines.dag_json` skeleton.
5. Run tests, confirm pass.
6. Commit: `feat(wizard): inspection spec upload + review with annotated overlay`

**Verification:**
- [ ] Upload + parse + approve flow completes end-to-end on reference fixture
- [ ] Approval correctly cascades to BOM items
- [ ] Low-confidence zones (< 0.7) are visually flagged
- [ ] Reviewer can edit a zone before approving (designator list, defect types, bbox)
- [ ] Audit fields populated (`approved_by`, `approved_at`)

## Risks + mitigation

| Risk | Mitigation |
|---|---|
| Form layouts vary across factories | YAML-defined template per customer; fallback to pure-VLM mode if heuristic fails |
| Scanned PDFs (not text PDFs) | Detect 0 text spans → skip Stage B, lean fully on Gemma vision + EasyOCR fallback |
| Gemma hallucinates designators not in BOM | Validate every extracted designator exists in `bom_items`; warn + drop if missing |
| Form has multiple PCB photos (front/back side stacked) | Detect via image clustering by aspect/position; align side-tag to whichever picture row |
| Defect type wording variants ("Pin Bending" vs "Connector Pin Bend" vs "Bent Pins") | Fuzzy match in `defect_detector_mapping.yaml` with synonyms list |
| Confidence threshold tuning | Start at 0.85 force-review; collect false-positive data; relax once stable |

## Roadmap items unlocked by this artifact

- **Auto-generate inspection report PDF after each production batch** — same template, fill `Inspection ✓` column with PASS/FAIL counts. Closes the loop with customer documentation requirements.
- **Diff two inspection specs** (revision tracking) — when customer engineering changes the form (e.g., new defect type added), highlight delta vs previously-approved spec.
- **Customer template library** — store per-customer form templates so subsequent PCB models from same customer parse with higher confidence on first try.
