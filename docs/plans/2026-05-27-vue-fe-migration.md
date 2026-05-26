# Vue Frontend Migration — Figma v1.5 (39 screens)

> Hybrid doc per gaspol-dev convention. **Design** section captured from `gaspol-brainstorm` 2026-05-27. **Implementation Plan** section will be appended by `gaspol-plan` when phase F0 starts.

## Design

### Context

After Figma redesign close (39 screens at fileKey `bbNj0YkQGJr2GpsvAaSS3R`, tracked in `~/.claude/projects/d--Projects-indusia-visual-editor/memory/figma-redesign-status.md`), backend M0–M14 is shipped and pushed to `origin/main` at commit `771bbbe`. The existing Vue frontend under `web/` carries pre-Figma styling and only partial screen coverage. This plan covers a **greenfield rewrite** to deliver full 39-screen Figma parity in 7 logical phases.

### Decisions locked (brainstorm 2026-05-27)

| Decision | Choice | Rationale |
|---|---|---|
| Scope | FE migration only | Backend M14 stays; M15 dual-mode endpoints deferred — engineer toggle handled client-side |
| Strategy | Greenfield rewrite | Cleaner than incremental given visual delta + new screens (Setup Eval, region-selected, Bundle E/F/D) |
| Transition | Wipe `web/` clean | Preserve `web/public/lsf/` (vendored LSF binary) + `web/.gitattributes` only; rebuild everything else fresh |
| MVP cut | All 39 screens — full Figma parity | ~7-9 weeks effort, single MVP target, no piecemeal release |
| i18n | `vue-i18n@10` with default `en` + ID switcher | Locale persisted in `localStorage['ive.locale']`; engineering jargon (Loss, mAP, F1) stays English in both locales |
| Engineer mode | localStorage-only (`localStorage['ive.advanced_mode']`) via Pinia hydration | No backend sync until M15; client-only is consistent with scope decision |
| Components | Reka UI (Radix Vue gen2) + Tailwind 3 | Accessible primitives + opinionated for keyboard-heavy canvas; bundle weight acceptable |
| Testing | Vitest (unit/component) + Playwright (e2e) full coverage | ~150-200 tests target; ~20% of total dev time |
| Mock data | MSW (Mock Service Worker) intercept axios | Dev-mode only; handlers in `web/src/mocks/handlers.ts`; swap to real API when backend endpoint lands |
| Branching | Direct push to `main` per CLAUDE.md §13.5 | No feature branches; one logical commit per phase F0–F6 |

### Tech stack (locked)

| Layer | Choice | Version |
|---|---|---|
| Framework | Vue 3 | `^3.5` (Composition API + `<script setup>`) |
| Build | Vite | `^7` |
| Language | TypeScript | `^5.6` (strict mode) |
| State | Pinia | `^2.3` |
| Router | vue-router | `^4.5` |
| Styling | Tailwind CSS | `^3.4` (with Geist + Geist Mono via `@fontsource`) |
| Primitives | Reka UI | `^2.x` (Radix Vue port) |
| HTTP | axios | `^1.7` (request interceptor stamps `Authorization: Bearer`; response interceptor catches 401 → refresh → replay) |
| i18n | vue-i18n | `^10` (Composition API mode) |
| Mocking | MSW | `^2.x` |
| Unit/Component test | Vitest + @vue/test-utils + happy-dom | `^2.x` |
| E2E test | Playwright | `^1.49` |
| Lint | ESLint flat config + Prettier + `eslint-plugin-vue` + `@vue/eslint-config-typescript` | latest |
| Package manager | pnpm | `^9` (matching Dockerfile builder) |

### Design tokens (per Figma)

| Token group | Value |
|---|---|
| Font family | `Geist` (UI), `Geist Mono` (mono, codes, metrics, kbd shortcuts) — no Inter |
| Primary | `#047857` emerald-700 (buttons, accent, active nav) |
| Primary hover | `#065F46` emerald-800 |
| Primary subtle bg | `#ECFDF5` emerald-50 (selected nav pill, status badges, banner) |
| Primary subtle border | `#A7F3D0` emerald-200 |
| Slate neutrals | `#0F172A` (text), `#475569` (muted), `#64748B` (placeholder), `#94A3B8` (disabled), `#CBD5E1` (border strong), `#E2E8F0` (border subtle), `#F1F5F9` (separator), `#F8FAFC` (sub-bg), `#FFFFFF` (canvas) |
| Engineer (purple) | `#7C3AED` ribbon, `#5B21B6` ribbon text, `#F5F3FF` card bg, `#DDD6FE` border, `#1E1B4B` log terminal bg, `#A5B4FC` terminal text |
| Warning amber | `#FDE68A` border, `#FFFBEB` bg, `#92400E` text, `#78350F` text strong |
| Error red | `#EF4444` accent, `#FEE2E2` bg, `#B91C1C` text |
| Info blue | `#DBEAFE` bg, `#1D4ED8` text |
| Border radius | `6`, `8`, `12` (cards), `16` (hero), `pill` (full) |
| Shadow | Subtle 1-px solid borders preferred over box-shadow (per Figma) |
| Screen size | 1440 × 810 (16:9) baseline — responsive collapses sidebar to 64w on small viewports |

### Execution phases

| Phase | Output | Acceptance gate |
|---|---|---|
| **F0 — Wipe + foundation** | Clean `web/` (preserve `public/lsf/` + `.gitattributes`); fresh Vite + TS + Pinia + Tailwind + Reka UI + vue-i18n + MSW + Vitest + Playwright; design tokens in `tailwind.config.ts`; ESLint + Prettier + tsconfig wired | `pnpm dev` boots, `pnpm test:unit` runs (0 tests OK), `pnpm test:e2e` boots Playwright |
| **F1 — Shell + primitives** | `AppShell`, `Sidebar` (brand + WORKSPACE/SETTINGS sections + AI avatar flush bottom), `TopBar` (breadcrumb + langSwitcher + themeToggle + engineerToggle), `ActionStrip` flush bottom, Button (primary emerald / ghost / disabled), Card, Pill (status / count), `EngineerRibbon` purple, ToggleSwitch, StatusPill, NumChip, Reka UI Dialog/Menu/Listbox wrappers | `/__dev/components` gallery renders all primitives in 2 locales × 2 modes |
| **F2 — Auth + Dashboard** | Login (6:2), Signup (6:48), Dashboard populated (8:2), empty (8:231), collapsed (69:46) — all EN+ID; `useAuthStore` + `api/auth.ts` connected to backend M14 `/api/auth/*`; refresh-cookie + bearer interceptor wired | Playwright: login → dashboard happy path; signup → dashboard happy path; bad creds → 401 envelope shown |
| **F3 — Project lifecycle** | Wizard step 1-5 + 3b/4b uploads (7 screens × EN+ID = 14 screens); BOM parser preview (SAP ZLMM_BOM_REPORT awareness — flatten + multi-designator expand + MI detect from Sort String); Golden samples upload (`POST /api/projects/{id}/assets` kind=golden_top/bottom); Drawing required gate; Project create end-to-end | Create project via UI → DB row exists → Wizard step 5 review summary correct |
| **F4 — Labeling workflow** | Labeling Canvas (LSF embed via `/lsf/main.{js,css}`); region-selected variant detail panel (X/Y/W/H/ID/criteria/4 action icons); Labeling correction mode banner ("Mode koreksi · 14 sampel salah"); dual-locale strings; AI auto-label removed (Refresh AI predictions only); Terapkan kriteria button + workflow tip | LSF onSubmit → backend label save passes; correction mode tile click → labeling correction view |
| **F5 — Training + Eval flow** | Gate 1 quartet (EN/ID × op/eng, training-mode picker + dataset readiness + considerations); Training quartet (epoch progress + per-component table + live metrics + considerations OR eng/techDetails); Setup Eval EN+ID (test set picker + readiness gates); Eval state A (failing) / B (corrected) / C (passed) screens with EN+ID + op/eng variants (12 eval screens total); threshold gate logic FE-side per spec §14 (mAP ≥ 0.80, F1 macro ≥ 0.80, per-component F1 ≥ 0.70) | Start training → SSE → Setup Eval → Eval verdict → state machine A→B→C |
| **F6 — Gate 2 + supporting + polish** | Gate 2 quartet ("Konfirmasi pasang model" with eng/techDetails for SHA256/registry/rollback/push command); Models (MSW mock); Edges (real API M11); Datasets (MSW mock); Team (MSW mock); Preferences (localStorage); ChatDrawer overlay (SSE chat M12 real); Toast system (3 variants); Promote modal interception; Bundle D real wires (drawer toggle, toast triggers, modal); final Playwright e2e + operator playtest | Full realistic flow end-to-end + Bundle D triggers verified |

### File layout (target after F6)

```
web/
├── public/
│   └── lsf/                  ← UNTOUCHED (vendored LSF binary)
├── src/
│   ├── api/                  ← axios clients (auth, projects, assets, bom, labels, training, eval, deploy, edges, chat)
│   ├── assets/               ← static (logos, icons, SVGs)
│   ├── components/
│   │   ├── primitives/       ← AppShell, Sidebar, TopBar, ActionStrip, Button, Card, Pill, ToggleSwitch, etc.
│   │   ├── canvas/           ← LSFEmbed, RegionDetailPanel, ChipPalette, WorkflowTip
│   │   ├── training/         ← ProgressStrip, PerComponentTable, LiveMetricsCard, EngTechDetails
│   │   ├── eval/             ← VerdictBanner, MetricCard, FilterBar, PredictionGrid, ThresholdGates
│   │   ├── gate/             ← Gate1Card, Gate2Card, ConfirmRow, OfflineWarn
│   │   └── overlays/         ← ChatDrawer, Toast, PromoteModal
│   ├── composables/          ← useEngineerMode, useLocale, useApi, useSse, useToast
│   ├── i18n/
│   │   ├── index.ts
│   │   └── locales/{en,id}.json
│   ├── locales/              ← (alias for i18n/locales/, per vue-i18n convention)
│   ├── mocks/                ← MSW handlers + browser worker init
│   ├── router/
│   │   └── index.ts          ← /, /login, /signup, /projects, /projects/:id/wizard, /labeling, /gate1, /training/:runId, /eval/:runId, /eval/:runId/gate2, /models, /edges, /datasets, /team, /preferences
│   ├── stores/               ← Pinia: auth, projects, wizard, labels, training, eval, deploy, edges, chat, ui (eng mode, locale, drawer)
│   ├── styles/
│   │   ├── tokens.css        ← CSS vars from design tokens
│   │   └── tailwind.css      ← @tailwind directives
│   ├── views/                ← page-level components matching routes
│   ├── App.vue
│   └── main.ts
├── tests/
│   ├── unit/                 ← Vitest stores + utils
│   ├── component/            ← Vitest @vue/test-utils
│   └── e2e/                  ← Playwright happy-path + cross-locale + cross-mode
├── .eslintrc.cjs / eslint.config.mjs
├── .prettierrc
├── Dockerfile                ← preserved (M14.1 multi-stage builder → nginx)
├── nginx.conf                ← preserved
├── index.html                ← regenerated (references /lsf/main.js + /lsf/main.css)
├── package.json              ← regenerated with new deps
├── pnpm-lock.yaml            ← regenerated
├── tailwind.config.ts        ← new (tokens + plugins)
├── postcss.config.js
├── tsconfig.json             ← strict mode
├── vite.config.ts
└── playwright.config.ts
```

### Data integration map

| Screen | Pinia store | API/source | Notes |
|---|---|---|---|
| Login / Signup | `useAuthStore` | `POST /api/auth/{signup,login,refresh,logout}` + `GET /api/auth/me` | Real — JWT bearer + refresh cookie |
| Dashboard | `useProjectsStore` + `useUiStore` | `GET /api/projects` (org-scoped per M13.4) | Real — compose card data FE-side |
| Wizard | `useWizardStore` + `useProjectsStore` | `POST /api/projects`, `POST /api/projects/{id}/assets`, `GET /api/projects/{id}/bom_items` | Real |
| Labeling | `useLabelsStore` + `useLsfStore` | `GET /api/projects/{id}/labels/task`, `POST /api/projects/{id}/labels`, `POST /api/projects/{id}/llm/prelabel` | Real + vendored LSF |
| Gate 1 | `useDatasetStatsStore` + `useTrainingStore` | `GET /api/projects/{id}/dataset/stats`, `POST /api/projects/{id}/training/suggest-hyperparams` | Real |
| Training | `useTrainingStore` | `POST /api/projects/{id}/training/start`, `GET /api/training/{run_id}/stream` SSE | Real |
| Setup Eval | `useEvalStore` | **MSW** `/api/projects/{id}/eval/setup` (mock) | Placeholder until backend endpoint |
| Eval A/B/C | `useEvalStore` | `GET /api/training/{run_id}/eval` | Real + FE-side threshold logic per spec §14 |
| Gate 2 | `useDeployStore` + `useEdgesStore` | `POST /api/projects/{id}/deploy`, `GET /api/edges` | Real |
| Models | `useModelsStore` | **MSW** `/api/models` | Mock |
| Edges | `useEdgesStore` | `GET /api/edges` + `PUT /api/edges/{id}` + `/pin` | Real |
| Datasets | `useDatasetsStore` | **MSW** `/api/datasets` | Mock |
| Team | `useTeamStore` | **MSW** `/api/team` | Mock |
| Preferences | `useUiStore` | `localStorage['ive.*']` | Client-only |
| ChatDrawer | `useChatStore` | `POST /api/chat/{session_id}/stream` SSE | Real |

### Anti-AI-slop self-check (per CLAUDE.md §12)

- ❌ "leverage / synergies / paradigm shift" — none in copy
- ❌ Emoji in UI strings — none (per CLAUDE.md)
- ❌ Hype language — none
- ❌ `TODO / FIXME / placeholder / mock` left in shipped code — MSW handlers explicitly named and isolated to `src/mocks/`, not infiltrating component code
- ❌ Bahasa "Inggris-tinggi" (sinergi/leverage/revolusi) — copy uses concrete verbs ("Mulai pelatihan", "Pasang model", "Refresh prediksi AI")
- ✅ Operator-friendly Bahasa Indonesia default? Decision: default English per user pick. Operator pabrik MI dapat switch ke ID via topbar pill.

### References

- Figma file: `bbNj0YkQGJr2GpsvAaSS3R` (Indusia Visual Editor — UI Redesign v1.5)
- Figma redesign status: `~/.claude/projects/d--Projects-indusia-visual-editor/memory/figma-redesign-status.md`
- Spec source of truth: `docs/specs/ml-workflow-dual-mode.md`
- Adoption spec (LSF boundary): `docs/specs/label-studio-adoption.md`
- LSF build spec: `docs/specs/lsf-build.md`
- Backend plan (M0–M14): `docs/plans/2026-05-22-visual-editor-mvp.md` + `docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md`

---

## Implementation Plan

_(To be appended by `gaspol-plan` when phase F0 starts. Reserved space for step-by-step execution plan with failing-test gates, atomic commits per CLAUDE.md "commit-per-phase" convention, and Iron Laws compliance.)_
