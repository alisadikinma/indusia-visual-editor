# LSF Build Verification — Phase 0.5 Spike Report

> Status: **VERIFIED (build + smoke test pass)** — 2026-05-22
> Verifies: `docs/specs/label-studio-adoption.md` §6.6 (Phase 0.5 prerequisite)
> Upstream source: `D:\Projects\label-studio` (NX monorepo, Apache-2.0)

---

## TL;DR — verdict

**APPROVED.** LSF can be built locally and embedded in our Vue 3 app. `window.LabelStudio` is exposed, canvas mounts cleanly, zero console errors. Adoption strategy in §6.6 of the adoption spec is feasible — BUT the adoption spec has 3 inaccuracies that this document corrects (see §6 below).

---

## 1. Environment that worked

| Item | Version | Notes |
|---|---|---|
| OS | Windows 11 | PowerShell host |
| Node | 24.14.0 | via nvm-windows |
| Corepack | 0.34.6 | bundled with Node 24 |
| Yarn | 1.22.22 (classic) | invoked via `corepack yarn@1.22.22 ...` — see §2 |
| Python | 3.12.10 | for static smoke server only |
| Browser | Chromium (Playwright headless) | smoke test runner |

**Yarn version is non-negotiable.** `D:\Projects\label-studio\web\yarn.lock` is `lockfile v1` (yarn 1.x format). Yarn 4 (corepack default) would rewrite to v8 format and break determinism. Always pin `@1.22.22`.

## 2. Reproduce — exact commands

From a clean shell in the upstream repo:

```powershell
# one-time toolchain prep
corepack prepare yarn@1.22.22                # downloads to corepack cache; no shim needed
# (do NOT run `corepack enable` — fails with EPERM on nvm-windows global dir)

# install deps (one-time per upstream commit, ~10 min, ~750 MB node_modules)
Set-Location D:\Projects\label-studio\web
corepack yarn@1.22.22 install --frozen-lockfile --network-timeout 600000

# build LSF library bundle (production, ~4 min)
$env:MODE = "standalone"
$env:NODE_ENV = "production"
corepack yarn@1.22.22 nx run editor:build:production
```

The `MODE=standalone` env var is critical — without it webpack builds the labelstudio SPA (`apps/labelstudio/src/main.tsx`) instead of the editor library (`libs/editor/src/standalone.js`). See `D:\Projects\label-studio\web\webpack.config.js` lines 73-134 for the branch.

## 3. Output artifact

```
D:\Projects\label-studio\web\dist\libs\editor\
├── main.js                4.54 MB   ← entry, ES module, exposes window.LabelStudio
├── main.css               1.53 MB   ← injected styles
├── main.js.map           17.91 MB   ← source map (NOT shipped)
├── main.css.map           1.54 MB   ← source map (NOT shipped)
├── 29.js / 131.js / 352.js / 616.js / 710.js   ← async chunks (vendor split: react, mobx, etc.)
├── decode-audio.wasm      1.16 MB   ← AudioRegion dependency
├── Figtree-Regular.ttf      40 KB
├── Figtree-SemiBold.ttf     40 KB
├── 3rdpartylicenses.txt    285 KB   ← Apache 2.0 obligation: ship this verbatim
├── config.<hash>.xml         1 KB
├── index.html               16 KB   ← built-in smoke-test page (LSF demo)
└── public/                            ← demo images/audio/video — NOT vendored
    ├── favicon.ico
    ├── manifest.json
    ├── files/   (demo images, audio, video — ~50 MB, NOT needed for prod)
    └── images/  (logo, favicon, github mark)
```

**Total bundle to vendor into our app (excluding maps + demo `public/files`):** ~8.6 MB raw, gzip ≈ 2.0 MB.

## 4. Smoke test result

Served `dist/libs/editor/` via `python -m http.server 7777`. Opened `http://localhost:7777/` in Chromium (Playwright).

```js
// In-page evaluation:
{
  hasLabelStudio: true,          // window.LabelStudio is a function ✓
  hasHtx: true,                  // window.Htx (MobX store handle) exposed ✓
  labelStudioDiv: true,          // <div id="label-studio"> present ✓
  childCount: 1,                 // LSF mounted a child element ✓
  bodyHtmlLen: 15494             // page rendered ✓
}
// Console errors: 0
// Console warnings: 0
```

The built-in demo (`libs/editor/public/index.html` template) instantiates LSF with a sample image annotation task. It rendered successfully end-to-end.

## 5. Known build warnings (non-blocking)

Build completed with 7 webpack warnings, all of the form:

```
export 'default' (imported as 'styles') was not found in
  './<X>.prefix.css' (module has no exports)
```

Affected modules:
- `libs/editor/src/regions/TextAreaRegion.jsx` (4 sites)
- `libs/editor/src/tags/control/Taxonomy/Taxonomy.jsx` (3 sites)

Cause: CSS-modules `import styles from './X.prefix.css'` pattern, but our webpack CSS pipeline (lines 149-212 of `webpack.config.js`) strips the default export for `.prefix.css` files because they're meant to be globally-prefixed, not module-scoped.

Impact: those components fall back to no JS-applied class names. Visual: tiny CSS-class mismatch in TextAreaRegion + Taxonomy. **Not used in our v1 labeling config** (no `<TextArea>` or `<Taxonomy>` in §3 of the adoption spec example).

Action: ignore for v1. Track as upstream issue if we ever enable Taxonomy/TextArea features.

## 6. Adoption-spec corrections (`docs/specs/label-studio-adoption.md`)

These statements in the adoption spec are wrong; this doc supersedes them:

| Location in spec | Spec claim | Reality | Fix |
|---|---|---|---|
| §2.2(a) step 2-3 | `yarn install && yarn lsf:build` produces `web/libs/editor/dist/` | `lsf:build` script does NOT exist in `web/package.json`. The only LSF scripts are `lsf:watch` (dev) and `lsf:serve(-static)`. Actual production build command is `MODE=standalone yarn nx run editor:build:production`. Output goes to `web/dist/libs/editor/`, NOT `web/libs/editor/dist/`. | Use `corepack yarn@1.22.22 nx run editor:build:production` with `MODE=standalone` and `NODE_ENV=production`. Output dir is `web/dist/libs/editor/`. |
| §2.2(a) step 4 | "Copy `dist/main.js` + `dist/main.css` into our app's `web/public/lsf/`" | The bundle splits into multiple chunks (`29.js`, `131.js`, `352.js`, `616.js`, `710.js`) loaded dynamically by webpack runtime. Shipping only `main.js` + `main.css` will fail at runtime when a chunk is requested. Also need `decode-audio.wasm` + the two `Figtree*.ttf` fonts. | Vendor the ENTIRE built tree EXCEPT `*.map` + the demo `public/files/` directory. ~8.6 MB. Preserve directory structure verbatim. |
| §2.2(a) step 5 | `<script src="/lsf/main.js">` → `window.LabelStudio` becomes available | webpack 5 emits `<script src="main.js" type="module">` (ES module). Same-origin loading is fine, but `type="module"` enforces stricter CORS rules + defers execution. Plus the runtime needs to load chunks from the same dir. | Load via `<script type="module" src="/lsf/main.js"></script>` and serve all sibling files (chunks, css, wasm, fonts) from `/lsf/`. Same effect as the spec intended, but use the correct attribute. |

Action items (not in this spike — flag for user approval):
- [ ] Edit `docs/specs/label-studio-adoption.md` §2.2 with corrections above
- [ ] Update plan `docs/plans/2026-05-22-visual-editor-mvp.md` §6.6 (Phase 0.5) build command
- [ ] Update plan M6 Phase 6.1 vendor command + paths

## 7. Vendor strategy for our project (Phase 6.1 input)

When M6 Phase 6.1 runs, the vendoring script will:

```powershell
# Source
$src = "D:\Projects\label-studio\web\dist\libs\editor"

# Destination in our app
$dst = "D:\Projects\indusia-visual-editor\web\public\lsf"

New-Item -ItemType Directory -Force -Path $dst | Out-Null

# Copy everything except source maps and demo media
robocopy $src $dst /MIR /XF "*.map" /XD "public\files"

# Verify
Test-Path "$dst\main.js"        # → True
Test-Path "$dst\main.css"       # → True
Test-Path "$dst\decode-audio.wasm"  # → True
```

Apache 2.0 obligation: keep `3rdpartylicenses.txt` next to the bundle, and add an entry to our app's NOTICE/about page citing HumanSignal + Apache 2.0.

## 8. Upstream commit pinned

Upstream `develop` HEAD at time of spike. Need to capture the commit SHA before Phase 6.1 vendoring so re-builds are deterministic.

```powershell
Set-Location D:\Projects\label-studio
git rev-parse HEAD       # → record this SHA in docs/specs/label-studio-adoption.md §2.2 + this doc
```

(Not captured here — do at vendor time, when artifact is actually shipped.)

## 9. Time budget actuals (vs estimate in §6.6)

| Step | Spec estimate | Actual | Notes |
|---|---|---|---|
| `yarn install --frozen-lockfile` | "30 min cold, 5 min hot" | ~10 min cold | NX monorepo, 1463 packages, 746 MB |
| `yarn lsf:build` (corrected: `nx run editor:build:production`) | (none) | 237 s (~4 min) | webpack 5 production with terser + cssnano |
| Smoke test | (none) | ~10 s | python http.server + Playwright headless |
| **Total Phase 0.5 wall time** | "30 min total" | ~15 min | Fits budget |

## 10. Risks not addressed in this spike (carry forward)

- **Konva perf on 300+ region PCBs** — adoption spec §7 risk row. Not tested here; benchmark in M6 Phase 6.9 smoke test with realistic dataset.
- **LSF UI branding leak** — Heartex footer + "LSF" title visible in built page. Need CSS-injection / interface-toggling strategy in `LSFEmbed.vue` wrapper.
- **`type="module"` + Vue 3 dev server** — Vite serves modules fine, but cross-origin from `:5173` Vue dev server to `/lsf/` may need proxy config. Validate in Phase 6.2.
- **Upstream API stability** — pinned to `develop` HEAD now. Future upgrades require re-running build + this smoke test.
