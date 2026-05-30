# Figma Redesign Plan — Stability Hardening Surfaces

> Companion to `2026-05-30-inspection-stability-hardening.md`.
> Operator decision 2026-05-30: **design new surfaces as real Figma frames BEFORE any FE modification.**
> File: `bbNj0YkQGJr2GpsvAaSS3R`.

## State of the Figma file (verified 2026-05-30 via get_metadata, node 1:3)

The file has **two pages**: `0:1` **Foundations** (token library) and `1:3` **Screens** (46 screen frames).
The initial page-list call surfaced only Foundations; the Screens page is the real design surface.

**Foundations (`0:1`) tokens:** surface (canvas/raised/sunken/inverse/overlay), text (primary/secondary/
tertiary/inverse/onPrimary), border (subtle/default/strong/focus), primary (base/hover/pressed/subtle),
status (success/warning/danger/info/neutral — each base + subtle); Inter (Display 40/48 → Caption 11/16)
+ JetBrains Mono; spacing 2→64; radius none→full. (Stray `__wire_verify_TEMP` text node at root — clean up.)

**Screens (`1:3`) — 46 frames, all 1440×810.** File convention: **EN + ID twins** for every screen, plus
**state variants**. Shell = `Sidebar (240) + main (1200)`; `main` = `Topbar + body (+ actionStrip)`.
Relevant existing screens (node-ids for navigation):

- Auth: Login `6:2` / Signup `6:48` (+ ID `37:2` / `37:89`)
- Dashboard: populated `8:2`, empty `8:231`, collapsed `69:46` (+ ID twins)
- **Wizard**: `45:2`; Step1 `65:2`; **Step3 `65:268`** + **both-uploaded `82:2`**; Step4 `65:534`/`82:236`; Step5 `65:800`
- **Labeling**: `46:2`; correction-mode `166:2`; region-selected `199:2`
- **Gate 1**: `47:2`; Training-prep EN `121:2` / eng `124:2` (+ ID `126:8` / `126:209`)
- Training (run): `89:2`; EN `171:2` / eng `171:141` (+ ID `171:288` / `171:427`)
- **Setup eval**: EN `179:2` (testSetCard `179:65` → holdout `179:68` / newRun `179:75` / upload `179:81`); ID `179:123`
- Eval: `92:2`; state-B `147:2`; state-C `150:2`
- Gate 2 / Confirm deploy: `95:2`; EN operator `159:2` / engineer `160:2` (+ ID `163:2` / `163:131`)
- Settings: Models `99:2`, Edges `99:441`, **Datasets `99:852`**, Team `105:2`, Preferences `105:324`
- Overlays showcase: `107:2` (ChatDrawer `107:258`, Toasts, ModalPromote `107:310`)

**Implication (corrected):** screens already exist at full fidelity. New surfaces must **extend existing
screens** (as new state-variant frames) or be **new screens following the EN/ID-twin convention** — not
standalone component frames. No new color tokens required; existing status palette covers every state.

## Surface → Figma action map

| # | Surface | Existing Figma node | Action | States to draw |
|---|---|---|---|---|
| S1 | Multi-golden upload + thumbnail strip | Wizard Step3 `65:268` / both-uploaded `82:2` (single-upload today) | **Extend** — new variant "Wizard Step 3 (multi-golden)" EN+ID | empty · 1 board · N boards · drag-over |
| S2 | Golden QC badge (blur/exposure) | none (only "JPEG quality ≥ 85" copy `65:1159`) | **Add** to S1 variant, per thumbnail | pass · warn · fail |
| S3 | Registration pre-flight panel | partial — fiducial hints only (`65:1153`, chips `113:18`) | **Add** section to Gate 1 `47:2` → new variant EN+ID | checking · pass ✓ · fail ✗ (hard-stop + reason) |
| S4 | Low-confidence region chip + canvas overlay | partial — prelabel exists, no confidence UI; filter `113:56` | **Add** to Labeling `46:2` → new variant EN+ID | count chip · highlighted region |
| S5 | Locked test-set indicator | exists — Setup eval testSetCard `179:65`, Gate1 split `47:135` | **Extend** `179:65` (+ ID `179:123`) with lock state | locked (frozen split) · sample counts |
| S6 | Drift status card + re-validate CTA | minimal — post-deploy checkbox `159:123` only | **Add** — new "Monitoring" section on Models `99:2` OR new screen EN+ID | healthy · drifting >5% · alarm |
| S7 | Operator feedback (escape/overkill) | greenfield — zero hits | **New screen** "Inspection feedback" EN+ID, full shell | mark escape · mark overkill · resolved |
| S8 | Defect-library counts per class | greenfield — Datasets has summary counts only (`99:1170`) | **Add** section to Datasets `99:852` (+ any ID twin) | per-class accumulating counts |

### Convention compliance (mandatory for parity)
Every new/extended frame ships its **ID (Bahasa Indonesia) twin**, reuses the `Sidebar + main` shell,
binds **foundation variables** (not hardcoded hex), and matches existing state-variant naming
(`Screen / <Name> (<state>)`). Operator-facing copy in Bahasa Indonesia; technical terms in English.

## Token gaps assessment
- QC pass/warn/fail → success/warning/danger (exist). ✓
- Registration pass/fail → success/danger (exist). ✓
- Drift healthy/drifting/alarm → success/warning/danger (exist). ✓
- Low-confidence overlay → warning/subtle as a semi-transparent canvas fill (exist; set opacity). ✓
- Escape/overkill → danger/warning (exist). ✓
- **Conclusion: no new color tokens.** Possible additions only if review finds them: a dedicated
  canvas-overlay opacity token and a Mono "metric-delta" text style — both optional, decided during draw.

## Build order (matches stability tiers)
1. **Cleanup** — delete `__wire_verify_TEMP`; create "Stability Surfaces" page.
2. **Tier 1 frames** — S1, S2, S3 (input integrity, highest leverage).
3. **Tier 2 frames** — S5, S6, S7 (trust over time).
4. **Tier 3 frames** — S4, S8 (data maturity).

## Execution mechanics (MANDATORY before any Figma write)
- Load **/figma-use** before every `use_figma` call, and **/figma-generate-design** before translating
  any surface into Figma. Skipping them causes known failures.
- Reference the live Vue views for visual language: read the current component code (e.g.
  `web/src/views/WizardView.vue`, `Gate1View.vue`, `LabelingView.vue`) and/or screenshot the running app
  so the new surfaces match shipped styling, since Figma has no screens to copy from.
- Bind frames to the existing foundation **variables** where possible (not hardcoded hex) so the surfaces
  stay theme-correct (light default + dark toggle).

## Build progress (live in Figma, page `1:3` Screens)

**ALL 8 SURFACES DONE (2026-05-30) — edited in place on the originals so the prototype reflects them.**

**Tier 1:**
- **S1 + S2** — edited **in place** on the original `Screen / Wizard Step 3 (both uploaded)` **`82:2`**
  (`dzTop 82:158`, `dzBottom 82:218`): multi-board strips B1/B2/B3 + "Tambah" tile, per-side QC summary
  chip, per-board QC badges (OK/Blur), subtitle + note bar rewritten. (Side clone `244:2` was used to
  prototype the look, then deleted.) (Wizard mono-language → no twin. NOTE: empty-state frame `65:268`
  still single-upload — update separately if the prototype routes through it.)
- **S3** — registration pre-flight bar on Gate 1 **EN `121:2`** (bar `258:2`) + **ID `126:8`** (bar
  `261:2`), between Training-mode and action strip (shifted to y672). PASS state, hard-stop rule in copy.

**Tier 2 — DONE (2026-05-30):**
- **S5** — LOCKED indicator + frozen-split copy on Setup eval holdout option: EN `179:68` (pill `264:2`) +
  ID `179:189` (pill `266:2`). Conveys: same split reused every retrain → Gate-2 metrics comparable.
- **S6** — drift monitoring banner on Models `99:2` (banner `269:2`), DRIFTING state + "Re-validasi
  sekarang" CTA; honestly framed as scheduled re-eval vs locked holdout, NOT live edge telemetry (v1.5).
  Models table shifted to y188/h500. (Settings screens mono-language → no twin.)
- **S7** — NEW screen `Screen / Inspection feedback (ID)` node **`272:2`** (cloned from Datasets `99:852`,
  gutted). Explainer banner (`273:2`, manual v1 / edge-live v1.5) + feedback table (`274:2`): recent
  inspections with verdict pills + escape ("Defect lolos") / overkill ("False call") chips + 2 resolved rows.

**Tier 2:**
- **S5** — LOCKED/TERKUNCI holdout indicator: Setup eval EN `179:68` (pill `264:2`) + ID `179:189`
  (pill `266:2`); frozen-split copy.
- **S6** — drift banner on Models `99:2` (banner `269:2`), DRIFTING + Re-validasi CTA; framed as
  scheduled re-eval vs locked holdout (not live edge telemetry). Table shifted to y188/h500.
- **S7** — NEW screens `Screen / Inspection feedback (ID)` `272:2` + `(EN)` `279:2`; explainer banner +
  escape/overkill marking table with resolved rows.

**Tier 3:**
- **S4** — low-confidence chip (`289:2`) in Labeling `46:2` action row ("3 prediksi low-confidence").
- **S8** — defect-library card (`292:2`) on Datasets `99:852`: per-class accumulating counts; dataset
  cards shifted to y232/y548.

**S1/S2 upload UX revised (2026-05-30):** each side card is now a clear 3-part layout — header → explicit
dashed **upload zone** ("Seret atau klik · bisa banyak foto sekaligus") → photo-look thumbnails with ×
remove + QC badge. Applied to BOTH Wizard Step 3 states: complete `82:2` (3 boards/side) and in-progress
`65:268` (top 2 boards, bottom empty "0 board · min. 3" + Kosong chip). Old single-photo-per-side design
fully replaced.

**Wizard Step 4 PCB drawing → top + bottom, MULTI-IMAGE per side (2026-05-30, operator override):** split
the single 720px `dzDrawing` into two 352px cards, each a **multi-image** uploader (upload zone +
line-art drawing thumbnails D1/D2 with × remove + `N file` count chip) — same pattern as golden, distinct
thumbnail style (component-outline line-art vs golden's dark PCB photo). Empty `65:534` (dzTop `65:1166` +
dzBottom `303:11`, "Kosong"); uploaded `82:236` (dzTop `82:454` + dzBottom `304:22`, 2 files each). Note
"AI pakai semua drawing...". (Operator chose multi-image over the one-canonical-layout-per-side default.)

**S7 nav + prototype wiring (2026-05-30):** added a WORKSPACE "Umpan balik"/"Feedback" nav item with a
speech-bubble icon — ACTIVE on feedback screens (ID `272:2` item `311:2`, EN `279:2` item `313:2`),
INACTIVE + `ON_CLICK→NAVIGATE` reaction on Dashboard EN `8:2`→`279:2` (item `314:2`) and Dashboard ID
`37:177`→`272:2` (item `314:12`). Working prototype path: Dashboard → Feedback. **Caveat:** the Sidebar is
a DUPLICATED frame (not a component), so the item only appears on these 4 frames. To show it on all ~40
screens, either componentize the Sidebar (recommended — propagates) or add per-frame. Deferred pending
operator decision.

**Outstanding follow-ups (minor):** roll the Feedback nav item to all screens (componentize Sidebar vs
per-frame); optional S3 fail-state variant (registration > tolerance); Step-4 "Wajib"/"Opsional" label
mismatch between the two drawing frames (pre-existing, not introduced here).
Then FE implementation — backend/data work (opencv registration, golden QC, multi-golden payload, drift
re-eval, defect library) has no Figma dependency and can run in parallel.

## Handoff
After frames are approved in Figma → resume the stability implementation plan
(`2026-05-30-inspection-stability-hardening.md`) Tier 1 → 2 → 3 for FE. Backend/data work (opencv,
registration service, schema, drift re-eval) has no Figma dependency and may start in parallel.
