# CLAUDE.md — Indusia Visual Editor

> **Authoritative project memory.** Auto-loaded into every Claude Code session in this directory. Read this BEFORE exploring code, BEFORE making assumptions about existing modules, BEFORE generating new code. Updating this file is mandatory whenever a phase ships new routes, hooks, tables, services, or convention changes.

---

## 1. Project identity

| Field | Value |
|---|---|
| Name | `indusia-visual-editor` |
| One-line | Factory-user-driven PCB inspection platform — BOM + golden sample → production inspection in hours, no YAML, no CLI |
| Primary user | MI division operator / supervisor at PCB factories (non-coder) |
| Repo root | `D:\Projects\indusia-visual-editor` |
| Status | Backend M0–M14 ✓ + Frontend F0–F6 ✓ closed 2026-05-27 (Vue greenfield rewrite — full 39-screen Figma parity: auth + dashboard + wizard + labeling + gate1 + training SSE + setup-eval + eval state machine + gate2 + 5 settings views + ChatDrawer + ToastStack — see [docs/plans/2026-05-27-vue-fe-migration.md](docs/plans/2026-05-27-vue-fe-migration.md); 36 unit/component + 8 Playwright e2e green). Previous v1.5R "Refresh predictions" UX shipped 2026-05-26 (`web/src/stores/labels.ts` adds `refreshing` state + `refreshPredictions(projectId)` action that calls existing `apiRunPreLabel(projectId, this.side)` then re-fetches task JSON via `apiGetTask(projectId, this.side)` — predictions surface in the next LSFEmbed mount because LSFEmbed already watches `props.task` and tear-down/rebuilds on change; `web/src/views/LabelingView.vue` adds a "Muat ulang prediksi" button in the header (disabled while `store.refreshing || store.loading || !store.task`) + Bahasa Indonesia "Membuat prediksi baru dari Gemma..." indicator below the header; **no backend, schema, route, or env-var changes** — pure UX delta riding M5 prelabel orchestrator; PRE-IMPLEMENTATION SPIKE found zero `ml_backend` references in the vendored LSF bundle confirming Label Studio's ML Backend protocol lives only in the Django side we explicitly do NOT adopt — so the originally-planned v1.5 "LSF ML Backend protocol" implementation (adoption spec §4) would have been dead code in our stack; +6 frontend tests = 54 frontend total) (M14 close shipped 2026-05-26: 14.1 production Dockerfiles — backend `Dockerfile.api` multi-stage builder/dev/runtime with python:3.12-slim runtime + libpq5 + libgomp1 + non-root `ive` uid 10001 + uvicorn `IVE_APP_WORKERS=${IVE_APP_WORKERS:-2}` (image 205MB); frontend `web/Dockerfile` builder node:24-alpine + pnpm → runtime nginx:1.27-alpine on :8080 + immutable hashed-asset caching + SPA index fallback + /healthz (image 61MB); `.dockerignore` excludes tests/docs/.git/storage/models/registry/node_modules + whitelists `!README.md` (Poetry needs it for project resolution); `tests/spike/test_docker_prod_builds.py` opt-in `IVE_DOCKER_SPIKE=1` builds both images, asserts size ceiling + non-root user; 14.2 Traefik v3 file provider — `infra/traefik/traefik.yml` static config with :80+:443 entrypoints, HTTP→HTTPS permanent redirect, Let's Encrypt resolver via httpChallenge; `infra/traefik/dynamic.yml` two routers (api.indusia.example → api:8002, indusia.example → web:8080) both TLS+certResolver=letsencrypt+secure-headers middleware (HSTS preload+nosniff+XSS+referrer-policy); `docker-compose.prod.yml` traefik+api+web+postgres+backup-scheduler on split `ive-edge` (public) + `ive-internal` (internal:true so postgres has no host port) networks; `tests/spike/test_traefik_config.py` YAML schema validation for static + dynamic + compose; 14.3 Postgres backup automation — `infra/scripts/pg_backup.sh` runs inside the ive-postgres container via ofelia `@daily`, pg_dump --format=custom --no-owner --no-privileges | gzip --best to timestamped `ive-<YYYYmmdd-HHMMSS>.dump.gz`, optional S3 upload (skipped if `IVE_BACKUP_LOCAL_ONLY=1`), local retention via `find -mtime +RETENTION_DAYS -delete` (default 14d); `infra/scripts/pg_restore.sh` accepts local path OR s3:// URL, decompresses to tempdir, runs `pg_restore --clean --if-exists --no-owner --no-privileges` (idempotent drop+recreate); `tests/spike/test_pg_backup_roundtrip.py` opt-in `IVE_PGBACKUP_SPIKE=1` validates script presence + shebang + required env vars; 14.4 structured logging — `src/indusia_visual_editor/utils/logging_config.py` `configure_logging(mode, *, stream=None, level)` is the single entry point ("prod" → JSONRenderer one record per call, "dev" → ConsoleRenderer key=value), `merge_contextvars + add_log_level + TimeStamper(iso,utc) + StackInfoRenderer + format_exc_info` shared processors, `PrintLoggerFactory(file=target)` so `add_logger_name` was dropped (PrintLogger has no .name) and `get_logger(name)` binds `logger=<name>` manually via `structlog.get_logger().bind(logger=name)`; `bind_context(**kvs)` + `clear_context()` wrap structlog contextvars; `AppConfig.log_mode` (env `IVE_LOG_MODE`, default `prod`); `main.py` `RequestContextMiddleware` (BaseHTTPMiddleware) stamps `request_id` + `method` + `path` into contextvars on dispatch, echoes `X-Request-ID` response header, `clear_context()` on response so background tasks scheduled by the next request don't inherit; migrated 12 call sites from `logging.getLogger(__name__)` to `get_logger(__name__)` (routes/{adapt,chat,deploy,dataset_stats,edges,training} + services/{asset/bom_parser,edge/notify,llm/{chat,hyperparams,planner,prelabel}}) — structlog's `make_filtering_bound_logger` preserves stdlib %-formatting compat so existing `logger.info("msg %s", arg)` keeps working unchanged; 14.5 OpenTelemetry spans — `src/indusia_visual_editor/utils/otel_config.py` `configure_otel(endpoint=None, *, service_name)` idempotent global TracerProvider install, honors `OTEL_EXPORTER_OTLP_ENDPOINT` env (no IVE_ prefix), no-op when endpoint unset so dev runs without a collector; `main.py` calls `configure_otel()` + `FastAPIInstrumentor.instrument_app(app)` (per-request `<METHOD> <route>` spans with http.status_code/http.target) + `HTTPXClientInstrumentor().instrument()` (outbound httpx spans for Ollama + edge HTTP); manual spans wrap four outbound boundaries — `ollama.generate` / `ollama.chat` / `ollama.stream_chat` (llm.model + llm.message_count attrs; stream uses start_span+try/finally/end() because with-blocks don't compose across async-generator yields), `inspect_service.start_training` (inspect.model_dir attr), `edge.notify_edges` (edge.count + ok_count + fail_count tail attrs), `registry.push_model` (registry.pcb_name + failed_stage attr on non-zero exit); 14.6 runbook — `docs/runbook/deploy.md` first-time bootstrap (DNS A records + ACME http-01 flow + `.env.prod` template + Alembic upgrade head) + routine re-deploy + operator-visible signals (X-Request-ID, ofelia backup logs, ACME renewal) + rollback; `docs/runbook/disaster-recovery.md` three failure classes (postgres corruption via pg_restore.sh from S3, bad migration via alembic downgrade or full restore, bad-model promote via `PUT /api/edges/{id}/pin`) + full-host-loss recovery + quarterly drill cadence; `docs/runbook/onboarding.md` Bahasa Indonesia operator walkthrough 8 steps from project-create to Gate 2 promote in ~60 min with "what NOT to do" guard rails; `docs/runbook/README.md` index) [legacy M13 detail: 13.1 migration `0011_auth` adds `organizations` (UUID PK, slug UNIQUE) + `users` (UUID PK, email UNIQUE, password_hash, `role` CHECK in admin/engineer/viewer, FK to organizations ON DELETE CASCADE) + nullable `projects.organization_id` FK CASCADE + seed `default` organization at id `00000000-0000-0000-0000-000000000001` + back-fills existing projects; `services/auth/passwords.py` wraps `passlib bcrypt` with `verify_password` that never raises on bad/empty hash (login routes map all failure modes to a single 401 envelope); `bcrypt<4.1` pinned for passlib 1.7.4 compatibility; 13.2 `services/auth/jwt_service.py` HS256 `create_access_token` + `create_refresh_token` with distinct `type` claim (access carries `role`, refresh omits it so role changes force a re-resolve) + `verify_token(token) -> TokenPayload` + `InvalidTokenError` family; `routes/auth.py` exposes `POST /api/auth/signup` (201, sets refresh cookie + returns access token + UserRead), `POST /api/auth/login` (401 on bad creds OR unknown email — same envelope so probes cannot enumerate accounts), `POST /api/auth/refresh` (reads HttpOnly cookie, 401 if missing/invalid), `POST /api/auth/logout`, `GET /api/auth/me`; refresh cookie path=`/` samesite=`lax` httponly; `services/auth/user_crud.py` `create_user` with seed-org fallback and `DuplicateEmailError` (409 envelope); `services/auth/dependencies.py` `get_current_user` (401 envelope on missing/malformed/expired/wrong-type bearer), `get_current_user_optional` (returns None instead of raising — GETs that scope-when-authed), `require_role(*allowed)` factory; 13.3 bearer-token gate applied via `dependencies=[Depends(get_current_user)]` on every POST/PUT/DELETE across projects, assets, llm, adapt, labels, training, edges, deploy, chat (DECISION POINT LOCKED: GETs stay public in v1, viewer role uses them without auth — tightens in v1.5 SaaS multi-tenant); `tests/conftest.py` installs per-test `app.dependency_overrides[get_current_user] = _synthetic_user` (role=admin so legacy mutation tests keep god-mode) for ~330 legacy route tests; auth-test modules opt out by module path; 13.4 `services/auth/rbac.py` re-exports `require_role` + `require_admin` / `require_engineer` / `require_any` aliases; `routes/projects.py` `POST` and `PUT` require admin-or-engineer role, `DELETE` admin-only, `POST` sets `organization_id` from caller; `services/project/crud.py` `create_project(..., organization_id=...)` and `list_projects(..., organization_id=...)` accept opt-in org filter; `GET /api/projects` uses `get_current_user_optional` so logged-in callers get org-scoped view, unauth callers retain legacy unscoped behaviour; 13.5 `web/src/api/auth.ts` (`signup` / `login` / `refresh` / `logout` / `me`, all withCredentials), `web/src/stores/auth.ts` Pinia store persists access token in `localStorage['ive.access_token']` + `isAuthenticated` getter + `loadCurrentUser` + `logout` actions, `web/src/api/client.ts` request-interceptor stamps `Authorization: Bearer` on every call + response-interceptor catches 401 once, calls `/api/auth/refresh`, replays original request (no loop on auth endpoints), `web/src/views/LoginView.vue` + `SignupView.vue` Bahasa Indonesia forms with envelope-message error display + loading-state disabled submit, `web/src/router/index.ts` `/login` + `/signup` routes meta `public: true`, global `beforeEach` guard redirects to `/login` on protected paths + bounces already-authed users away from auth pages; `AppConfig` adds `auth_jwt_secret` (env `IVE_AUTH_JWT_SECRET`), `auth_jwt_algorithm=HS256`, `auth_jwt_ttl_seconds=3600`, `auth_refresh_ttl_seconds=14d`, `auth_refresh_cookie_name=ive_refresh`, `auth_refresh_cookie_secure=False` (flipped True behind Traefik HTTPS in M14)) [legacy M12 detail moved to commit ac907f3; new chat_sessions table from migration `0010_chat_sessions` — UUID PK + project_id FK CASCADE + JSONB `messages_json` server_default `'[]'` + created_at/updated_at TIMESTAMPTZ + `ix_chat_sessions_project_id`; `POST /api/projects/{id}/chat` (201 create), `GET /api/projects/{id}/chat` (list ordered by created_at), `GET /api/chat/{session_id}` (full transcript, 404 envelope); 12.2 `services/llm/chat.build_chat_context()` assembles `[system advisor.md prompt, project+last-3-train_runs-metrics block, last-MAX_TURNS=20 history, new user message]` in `OllamaClient.chat()`-shape, `TOKEN_BUDGET_CHARS=600_000` (~150K tokens at 4 char/tok, leaves Gemma 256K headroom for response), drops oldest history first; system prompt + project block + active user message are protected anchors; `prompts/advisor.md` is Bahasa Indonesia, concrete-next-step format, max-8-sentence tone, anti-corporate-speak; 12.3 `OllamaClient.stream_chat(model, messages) -> AsyncIterator[str]` opens `/api/chat` with `stream=true`, yields content deltas only (non-empty), stops on `done=true`, wraps transport errors into the existing `LlmError` family; `POST /api/chat/{session_id}/stream` (404 envelope on unknown session) builds context against clean pre-turn history, persists user turn via `_append_turn` short-lived session, opens upstream stream, relays each chunk as `data: {"delta": "..."}`, terminal `{"event":"done"}` or `{"event":"error","error":"..."}`, assistant text persisted regardless of stream outcome so audit trail stays clean; test seam `_llm_client_factory` + `set_llm_client_factory`/`reset_llm_client_factory` mirroring `routes/llm.py`; 12.4 `web/src/components/ChatDrawer.vue` floating `?` toggle bottom-right + slide-out panel, user bubbles `self-end` + assistant bubbles `self-start`, typing indicator while `store.streaming`, Bahasa Indonesia placeholder; `web/src/stores/chat.ts` Pinia store with `openSession` + `sendMessage` (pushes user bubble + empty assistant slot, live-updates as deltas arrive via async generator); `web/src/api/chat.ts` fetch+ReadableStream manual SSE parse for `streamReply` since `EventSource` can't POST a body; `web/src/App.vue` mounts drawer only when route has `:id` param]) | next: post-M14 polish & v1.5 (LSF ML backend / runtime defect judge / multi-tenant SaaS) |
| Plan (M0–M4) | [docs/plans/2026-05-22-visual-editor-mvp.md](docs/plans/2026-05-22-visual-editor-mvp.md) |
| Plan (M5–M14) | [docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md](docs/plans/2026-05-22-visual-editor-mvp-m5-m14.md) |
| Adoption spec | [docs/specs/label-studio-adoption.md](docs/specs/label-studio-adoption.md) |
| LSF build spec | [docs/specs/lsf-build.md](docs/specs/lsf-build.md) |
| Graphflow schema | [docs/specs/graphflow-config-schema.md](docs/specs/graphflow-config-schema.md) |

## 2. Current implementation state

Only commit history is authoritative — never invent state. As of 2026-05-26 (M14 close):

| Layer | Built | Not yet built |
|---|---|---|
| Backend | FastAPI app, `GET /health`, `POST /api/auth/signup` + `/login` + `/refresh` + `/logout` + `GET /api/auth/me` (M13.2), `/api/projects` CRUD (M13.4 role gates: POST/PUT admin+engineer, DELETE admin-only), `/api/projects/{id}/assets`, `/api/projects/{id}/bom_items` GET, `/api/projects/{id}/llm/plan` POST+GET, `/api/projects/{id}/llm/prelabel` POST+GET, `/api/projects/{id}/adapt` POST+GET, `/api/projects/{id}/labels/task` GET, `/api/projects/{id}/labels` POST+GET, `/api/projects/{id}/training/start` POST, `/api/projects/{id}/training` GET, `/api/training/{run_id}/stream` GET (SSE), `/api/training/{run_id}/eval` GET, `/api/projects/{id}/dataset/stats` GET, `/api/projects/{id}/training/suggest-hyperparams` POST, `/api/projects/{id}/deploy` POST+GET, `/api/edges` POST + GET + `PUT /api/edges/{id}` policy update + `PUT /api/edges/{id}/pin` rollback (M11), `POST /api/projects/{id}/chat` (201 create) + `GET /api/projects/{id}/chat` (list) + `GET /api/chat/{session_id}` (transcript, 404 envelope) + `POST /api/chat/{session_id}/stream` SSE (M12 chat advisor — all M11/M12 mutations bearer-gated via M13.3), DB models (Project / Asset / BomItem / ProposedPipelineRow / AdaptRun / PreLabel / Label / TrainRun / Deployment / Edge / ChatSession / Organization / User), `get_session` async dep, `services/auth/{passwords,jwt_service,user_crud,dependencies,rbac}.py`, exception handlers 404/409/413/422/502 + generic HTTPException return `{status, message, data}` envelope, fs storage at `IVE_STORAGE_ROOT` with SHA256 dedup, Ollama async client + `stream_chat()` AsyncIterator over NDJSON deltas, planner, prelabel orchestrator, `services/llm/chat.build_chat_context()`, `TrainingClient`, `compute_dataset_stats`, `suggest_hyperparams`, `services/deploy/registry.push_model`, `services/edge/notify.notify_edges`, BOM parser, MI/SMT heuristic classifier, inspect_scope deriver, graphflow adapter, **`utils/logging_config.py` (structlog + request_id middleware) + `utils/otel_config.py` (OTel TracerProvider + FastAPI/HTTPX auto-instrumentation + manual spans on 4 outbound boundaries) (M14.4 + M14.5)** | v1.5: LSF ML backend protocol, runtime defect judge, multi-tenant SaaS hardening |
| Tests | 347 backend + **36 frontend unit/component + 8 Playwright e2e = 391 total (FE migration F0–F6 close 2026-05-27)**. New FE stores tests: 6× `wizard.spec.ts` (initial state, slug autofill, canAdvance gate, project create on step1 transition, asset upload bookkeeping, bom items fetch on step2 transition), 4× `labels.spec.ts` (load+counts, switchSide reload, submit lastSavedAt, correction-mode toggle), 5× `eval.spec.ts` (verdict passed/failing/corrected per EVAL_THRESHOLDS, mAP below 0.80 → failing, wrongCount sums fp+fn), 5× `toast.spec.ts` (push variant, auto-dismiss 4s success, 6s error, dismiss by id, clear all). New FE component tests: 4× `LoginView.spec.ts` (renders, valid creds → token/user/route, 401 envelope error via MSW override, `?next=` honored), 4× `SignupView.spec.ts` (renders, password-mismatch role=alert, success → dashboard, 409 duplicate). 8× Playwright `auth-flow.spec.ts` (login → dashboard with 3 sample projects, signup → dashboard, password mismatch inline alert, protected route redirects with ?next= preserved, locale switcher EN↔ID swaps logout button, realistic flow login → New project → wizard step1 fill via placeholder locators → step2 heading + UUID URL rewrite) + 2 carry-over smoke (login page renders, unauthenticated redirected). Pre-existing FE tests: 3× auth.spec.ts (token persistence + logout + isAuthenticated), 2× engineer.spec.ts (toggle + persistence), 3× AppButton.spec.ts. M14 backend net-new: 4× `tests/utils/test_logging.py` 4× `tests/utils/test_logging.py` (prod JSON payload + dev console renderer + bind_context propagates to nested calls + clear_context drops request_id), 3× `tests/utils/test_otel.py` (no-endpoint configure is safe + manual span records name+attributes + nested spans share trace_id), opt-in spike tests `IVE_DOCKER_SPIKE` / `IVE_PGBACKUP_SPIKE` for Docker build + pg_backup round-trip, `tests/spike/test_traefik_config.py` 3× YAML schema validation (static + dynamic + compose). **New M13 backend tests: 4× `tests/services/auth/test_passwords.py` (hash non-deterministic + verify roundtrip + reject wrong + reject malformed-hash returns False not 500), 5× `tests/services/auth/test_jwt.py` (access roundtrip + wrong secret rejected + expired rejected + malformed rejected + refresh type-claim), 9× `tests/routes/test_auth.py` (signup happy + duplicate 409 + login happy + login wrong-password 401 + login unknown 401 + refresh via cookie + refresh no-cookie 401 + me with bearer + me without bearer 401), 20× `tests/routes/test_auth_middleware.py` (16 parametrised endpoint 401 probes + valid bearer not-401 + expired bearer 401 + malformed Authorization 401 + GET stays open), 5× `tests/services/auth/test_rbac.py` (engineer create + viewer create blocked 403 + engineer delete blocked + admin delete + cross-org list isolation), 5× ORM constraints (org+user roundtrip + email UNIQUE + role CHECK + cascade-from-org + project.organization_id assignable). New M13 frontend tests: 4× `auth.spec.ts` (login persists token + logout clears + bad login captures error + signup persists token), 4× `LoginView.spec.ts` (Bahasa heading renders + submit calls api.login + envelope error displayed + disabled while loading).** 3 opt-in Ollama + 1 opt-in inspect_service + 1 opt-in ais integration tests skip when env vars unset. | everything else |
| Frontend | **F0–F6 closed 2026-05-27** — Vue 3.5 + Vite 7 + TS strict + Pinia 2 + Tailwind 3 + Reka UI 2 + vue-i18n 10 + MSW 2 greenfield rewrite at `web/`. Routes: `/` Dashboard, `/login` + `/signup` (meta.public), `/projects/new` → redirects to `/projects/new/wizard`, `/projects/:id/wizard`, `/projects/:id/labeling`, `/projects/:id/gate1`, `/projects/:id/training/:runId`, `/projects/:id/setup-eval/:runId`, `/projects/:id/eval/:runId`, `/projects/:id/eval/:runId/gate2`, `/models`, `/edges`, `/datasets`, `/team`, `/preferences`; global `beforeEach` guard redirects unauthenticated callers to `/login?next=...` and bounces authed callers away from auth pages. Pinia stores: `useAuthStore` (token in `localStorage['ive.access_token']`, `isAuthenticated` getter, `login` / `signup` / `loadCurrentUser` / `logout` actions, `error`+`loading` state), `useProjectsStore` (fetchAll + create + byStatus computed), `useWizardStore` (5-step state machine with slug autofill + createProject step1 + uploadAsset step2-4 + fetchBomItems step2 + canAdvance gate), `useLabelsStore` (loadTask + switchSide + refreshPredictions + submit + correctionMode state with sampleIds), `useTrainingStore` (loadGate1 composes stats+hyperparams+per-component queue, start, openStream wraps EventSource parsing running/epoch/succeeded/failed events updating live metrics + perComponent + 50-line log buffer, closeStream on unmount), `useEvalStore` (verdict state machine failing/corrected/passed via classifyEval against EVAL_THRESHOLDS mAP 0.80 / F1 macro 0.80 / per-comp F1 0.70, failingComponents filter, canPromote), `useDeployStore` (promote + history), `useEdgesStore` (fetchAll + unpin with onlineCount/offlineCount computed), `useChatStore` (drawerOpen + ensureSession + sendMessage with rolling assistant bubble update via async generator), `useToastStore` (push/success/warning/error with TTL auto-dismiss timer 4s success+warning / 6s error), `useUiStore` (locale + sidebarCollapsed localStorage persistence), `useEngineerStore` (toggle persistence). Axios clients: `api/{auth,projects,assets,bom,labels,training,eval,deploy,edges,chat}.ts`; `api/client.ts` request-interceptor stamps `Authorization: Bearer <token>` + response-interceptor catches 401 once, calls `/api/auth/refresh`, replays original request (no loop on auth endpoints). `api/chat.ts streamReply()` is an async generator manually parsing chunked SSE from `fetch()` because EventSource can't POST a body. `api/eval.ts` exports `EVAL_THRESHOLDS` + `classifyEval(metrics, hasCorrections)` pure-FE verdict logic per spec §14. Layout: `components/layout/{AppShell, AppSidebar, AppTopBar}.vue` — AppShell mounts ChatDrawer + ToastStack overlays globally; AppSidebar has brand + WORKSPACE section (Dashboard) + SETTINGS section (Models/Edges/Datasets/Team/Preferences all real routes) + AI advisor flush bottom, collapsible via ui.sidebarCollapsed; AppTopBar has breadcrumb (from `route.meta.titleKey`) + EN/ID pill switcher + engineer-mode toggle pill + user email/role + logout. Canvas components: `components/labeling/{LSFEmbed, RegionDetailPanel}.vue` — LSFEmbed dynamic-loads `/lsf/main.{js,css}` via idempotent head-injected `<script>`+`<link>` (singleton window promise) and instantiates `window.LabelStudio({config, task, interfaces, instanceOptions:{reactVersion:'v18'}, onSubmitAnnotation/onUpdateAnnotation/onEntityCreate/onLabelStudioLoad})` wired to Vue emits, tear-down + rebuild on task/config change, fallback panel if script load fails. Overlay components: `components/overlays/{ChatDrawer, ToastStack}.vue` — ChatDrawer is floating `?` button bottom-right + slide-from-right drawer + project-scoped session ensure on open + typing animation while streaming + Enter-to-send/Shift+Enter newline + refuses to chat outside a project route; ToastStack is top-right stacked with TransitionGroup + 3 variant tones + dismiss button. Views: LoginView + SignupView (split 2-col with emerald gradient panel, envelope error display, password-mismatch guard on signup, honors `?next=` query), DashboardView (8:2 layout: 4 stat cards + projects table on left, quick-start + AI advisor + docs rail on right), WizardView (5-step stepper: project basics → BOM → golden samples → drawing → review with dropzone affordances + BOM preview table 50-row truncated + URL rewrite `/projects/new` → real UUID after step 1), LabelingView (action strip with top/bottom side toggle + designator/prediction counters + Refresh AI + Save + saved-at notice; amber correction banner from `?correction=1&samples=id1,id2`; LSF canvas left + RegionDetailPanel right with X/Y/W/H/R° + 8 defect-criteria checkboxes + 4 action icons; workflow-tip footer), Gate1View (HITL banner + 3-bucket dataset readiness + per-designator table + training-mode picker scratch SELECTED+continue DISABLED-tooltip + considerations + engineer-mode purple ENGINEER ribbon revealing hyperparams grid), TrainingView (status pill + progress strip epoch X/Y+ETA+% + per-component table Done/Training/Queued + live metrics card mAP/F1/P/R/Loss + engineer-mode reveals tech-details card with dark log terminal tailing 12 lines), SetupEvalView (HITL banner + 3-option test-set picker + readiness gates + duration estimate), EvalView (verdict-driven banner red/amber/primary + 4 metric tiles colored by threshold + clickable failing-components grid opens correction mode in Labeling + per-component table + verdict-routed action correctSamples/setupRetrain/promote), Gate2View (passed/blocked banner + model snapshot + edges card with online/offline + engineer-reveal tech-details SHA256+registry tag+rollback target+push command terminal + confirm-checkbox gate + modal interception + success/error toast), ModelsView (filter pills + table with status badge), EdgesView (4-stat cards + registry with unpin action), DatasetsView (kind badges), TeamView (role badges admin emerald / engineer purple / viewer slate), PreferencesView (account + EN/ID switcher + engineer-mode toggle wired to localStorage). i18n: full `en.json` + `id.json` with namespaces app/common/nav/auth/dashboard/wizard/status/labeling/criteria/gate1/training/setupEval/eval/gate2/models/edges/datasets/team/preferences/chat/engineer. MSW dev-mode handlers (`src/mocks/handlers.ts`) include persistent in-memory dbs (projectsDb, assetsDb with sha-from-first-8-bytes, bomDb with 10 sample rows R/C/U/J/D mix, trainRunsDb, edgesDb 4 seed edges with 3 online + EDGE-04 offline, modelsDb, datasetsDb, teamDb, chatDb) + scripted 30-epoch SSE training stream via ReadableStream emitting 150ms per epoch + word-by-word chat reply stream at 40ms/token + sample eval with J5 fail at F1=0.63 to trigger failing verdict. CORS allowed on backend for :5173 with `allow_credentials=True`. **Figma 100% redo closed 2026-05-30 (`docs/plans/2026-05-27-figma-100-redo.md`, 8 bundles): every view rewritten to pixel-faithful parity with Figma file `bbNj0YkQGJr2GpsvAaSS3R` using the §A.6 design tokens (border-default/surface-raised/primary-*). Routes + stores + view filenames UNCHANGED; new artifacts are `web/src/api/dashboard.ts` (typed `DashboardSummary`) + `useProjectsStore.fetchSummary()` reading `GET /api/dashboard/summary`. DashboardView is now a full-width bento (4 stat cards Active/Models/Edges/Avg-mAP + filter chips + featured hero + project-card grid). Hard honesty rule applied throughout — every view OMITS Figma affordances with no backing data rather than fabricate (no Dashboard trend-deltas/7-day-chart; no Wizard PCB-model dropdown or live "Gemma noted"; no Gate1 train-val-split/hold-out/image-size tiles; Training per-component table is designator+state only; SetupEval gate values labelled train/pending; no Eval TP-TN/pipeline-chips; Gate2 "computed on push" not a fake hash; Settings Models/Datasets/Team are mock-only read-only screens). FE test count now 126 (22 files); `vue-tsc` + `eslint` clean; `vite build` passes.** | LSF runtime smoke verification under prod nginx (manual playtest), skipped-region dim overlay runtime binding |
| Docker | Dev: `docker-compose.dev.yml` (postgres:16-alpine on host port 5433, named volume `ive-postgres-data`), dev `Dockerfile.api` + `web/Dockerfile`, `scripts/dev-{up,down}.ps1` helpers. **Prod: `docker-compose.prod.yml` (traefik v3 + api + web + postgres + ofelia backup-scheduler) on split `ive-edge` (public) / `ive-internal` (internal:true) networks, prod `Dockerfile.api` runtime stage 205MB non-root + `web/Dockerfile` runtime stage 61MB nginx; `infra/traefik/{traefik,dynamic}.yml` ACME httpChallenge + secure-headers middleware; `infra/scripts/{pg_backup,pg_restore}.sh` daily backup + S3 upload + retention (M14.1-14.3)** | — |
| DB | Alembic migrations 0001–**0011** applied: `projects` (+ M13 `organization_id` FK CASCADE), `assets`, `bom_items` (with `scope_mode` + `detector_presets` cols from 0006), `proposed_pipelines`, `adapt_runs`, `pre_labels`, `labels`, `train_runs`, `deployments`, `edges`, `chat_sessions`, **`organizations` (UUID PK, slug UNIQUE) + `users` (UUID PK, email UNIQUE, password_hash, role CHECK admin/engineer/viewer, FK organizations CASCADE) — seed org `00000000-...-0001` slug=`default` provisioned by 0011_auth so v1 single-tenant deploys keep working**. All downgrade→upgrade cycles clean. | Future migrations per phase |
| LSF | Vendored at `web/public/lsf/` (~7.5MB: main.js, main.css, 5 chunks, 2 fonts, WASM, XML config) via `scripts/vendor-lsf.ps1` (idempotent + sha256 manifest). `.gitattributes` pins as `-text` for cross-platform byte stability. `web/index.html` references `/lsf/main.js` + `/lsf/main.css`. Embedded via `LSFEmbed.vue` with `reactVersion: 'v18'`. Bundled in the prod `web` image via `web/Dockerfile` (M14.1). | Runtime smoke verification under prod nginx (manual) |
| Runbook | `docs/runbook/{README,deploy,disaster-recovery,onboarding}.md` (M14.6) — ops-engineer bootstrap + DR procedures + Bahasa Indonesia operator walkthrough | Quarterly DR drill cadence (first drill TBD) |
| Observability | structlog JSON logs to stdout with `request_id` contextvar middleware + `X-Request-ID` response header (M14.4); OpenTelemetry TracerProvider + FastAPI/HTTPX auto-instrumentation + manual spans on `ollama.{generate,chat,stream_chat}` / `inspect_service.start_training` / `edge.notify_edges` / `registry.push_model` (M14.5). Honors `OTEL_EXPORTER_OTLP_ENDPOINT` standard env. | OTel collector deploy + dashboards (operator concern) |
| Graphflow schema | spec documented (2-layer, 49 node types) + adapter shipped in M4 | Runtime smoke against real auto-inspect-service (M7) |

**Anti-hallucination rule:** if it isn't in the file tree or the git log, it doesn't exist. Run `git log --oneline` if uncertain.

## 3. External services (DO NOT modify)

These are sibling repos at `D:\Projects\Indusia-Inspection\`. We HTTP-call them; we never edit their code in v1.

| Service | Port | Role | Reuse pattern |
|---|---|---|---|
| `auto-inspect-service` | 8001 | Inference engine (graphflow + YOLO + Anomalib + fiducial + OCR + barcode) + Git+LFS model registry via `ais model push/pull` | We POST `/api/training/start`, subscribe to its SSE stream, call `/api/models/{name}/load` |
| `auto-inspect-edge` | 8000 | Hardware: PLC + Hikrobot camera, pulls weights via `ais model pull`, receives selected model from `.cache/selected_model.json` | We send refresh webhook only; otherwise untouched |
| `auto-inspect-engine` | (lib) | `BaseEstimator` / `BaseTransform` foundation, RGB everywhere | We do NOT import this directly in v1 — we configure it through service |
| Ollama | 11434 | `gemma4:31b` (20GB, 256K context) on dedicated GPU box | httpx async, structured-output mode |

**Iron law copied from `auto-inspect-engine`:** all custom model classes extend `BaseEstimator` / `BaseTransform`. RGB images everywhere, never BGR.

## 4. Tech stack — LOCKED

Do NOT substitute. If a need arises that doesn't fit, raise it as a plan deviation, never silently swap.

| Layer | Choice | Notes |
|---|---|---|
| Python | 3.10+ (Poetry resolved 3.14.3 on Ali's machine) | `requires-python = ">=3.10,<4.0"` |
| Web framework | FastAPI 0.121+ + uvicorn[standard] | Async-first |
| Config | pydantic-settings 2.x, env prefix `IVE_` | `.env` file optional |
| HTTP client | httpx (async) | NOT `requests` |
| ORM | SQLAlchemy 2.x async + Alembic | Phase 1.1 onward |
| DB | PostgreSQL 16 (Docker Compose) | Phase 0.4 onward |
| SSE | sse-starlette | for training progress relay |
| Image I/O | opencv-python + PyTurboJPEG | match engine |
| LLM client | httpx → Ollama `/api/generate` + `/api/chat`, `format=json` | structured-output validated by pydantic |
| Tests | pytest + pytest-asyncio (auto mode) + httpx ASGITransport | factory-boy when needed |
| Packaging | Poetry 2.x | venv per project |
| Frontend | Vue 3 + Vite + TS + Pinia + Vue Router | Phase 0.3 onward |
| Canvas | LSF (Apache-2.0) vendored at `web/public/lsf/` | NOT custom Konva; see §10 |
| Frontend HTTP | axios + native EventSource | for SSE consumption |
| Styling | Tailwind 3 + tokens from §A.6 of plan | NO ad-hoc colors |
| FE tests | Vitest + @vue/test-utils | |
| Containers | Docker Compose (dev + prod) | Phase 0.4 |
| Reverse proxy (prod) | Traefik (auto HTTPS) | M14 |
| Code style | black + isort + flake8 (Py); biome / eslint + prettier (Vue) | mirror existing services |

## 5. Backend file layout — canonical

This is the target structure. Create files in this exact layout. Do NOT invent alternative paths.

```
src/indusia_visual_editor/
├── __init__.py                 # __version__ source of truth
├── main.py                     # FastAPI app + lifespan + middleware + router wiring
├── config.py                   # AppConfig(BaseSettings), IVE_ prefix
├── routes/
│   ├── __init__.py
│   ├── projects.py             # Phase 1.2
│   ├── assets.py               # Phase 1.3 + 2.2
│   ├── labels.py               # M6
│   ├── training.py             # M7 (Gate 1)
│   ├── deploy.py               # M10 (Gate 2)
│   ├── chat.py                 # M12 advisor SSE
│   ├── llm.py                  # Phase 3.4 planner endpoint
│   ├── ml_backend.py           # M5/v1.5 LSF ML backend protocol
│   └── webhooks.py             # M11 edge integration
├── schemas/                    # pydantic request/response models
│   ├── projects.py
│   ├── assets.py
│   ├── labels.py
│   └── ...
├── services/
│   ├── asset/                  # BOM parser, image store, drawing proc, MI classifier
│   ├── project/                # CRUD + versioning
│   ├── label/                  # LS-JSON validate, region ops, exporter (LS→YOLO)
│   ├── llm/                    # planner, prelabel, judge (v1.5), advisor
│   ├── inspect_scope/          # derive scope+detector_presets from LSF annotation
│   ├── inspect_service/        # httpx client → auto-inspect-service
│   └── deploy/                 # promote-to-prod + edge notify
├── db/
│   ├── __init__.py
│   ├── session.py              # async engine + get_session dep
│   ├── models.py               # SQLAlchemy declarative
│   └── alembic/                # migrations
├── data/                       # YAML data files (taxonomy, detector mapping) — committed
└── utils/
    ├── logging_config.py
    └── responses.py            # success() / failed() — match existing service shape
```

## 6. Backend conventions

### 6.1 Response shape — MANDATORY

EVERY route returns this shape on both success and error paths. Match `auto-inspect-service` helpers exactly.

```python
{
    "status": True | False,
    "message": "human-readable string",
    "data": {...} | None,
}
```

`/health` is the reference: `{"status": True, "message": "ok", "data": {"version": "0.1.0"}}`.

### 6.2 Env vars

All env vars use the `IVE_` prefix. Defaults live in `AppConfig` (`config.py`). The `.env` file is optional and gitignored (`!.env.example` is not; `.env.example` is committed and is the schema doc).

Current keys:
- `IVE_APP_HOST` (default `0.0.0.0`)
- `IVE_APP_PORT` (default `8002`)
- `IVE_LOG_LEVEL` (default `INFO`)

Planned (add to `AppConfig` when needed, never read `os.environ` directly):
- `IVE_DATABASE_URL` — Phase 0.4
- `IVE_OLLAMA_URL` (default `http://localhost:11434`) — Phase 3.1
- `IVE_OLLAMA_MODEL_PLANNER` (default `gemma4:31b`) — Phase 3.1
- `IVE_OLLAMA_MODEL_PRELABEL` — Phase 3.1
- `IVE_OLLAMA_TIMEOUT` (default `120`) — Phase 3.1
- `IVE_INSPECT_SERVICE_URL` (default `http://localhost:8001`) — Phase 7+ (LIVE)
- `IVE_INSPECT_SERVICE_TIMEOUT` (default `30`) — Phase 7+ (LIVE; applies to unary start call only — SSE stream uses `timeout=None`)
- `IVE_STORAGE_ROOT` (default `./storage`) — Phase 1.3
- `IVE_AUTH_JWT_SECRET` (dev default `dev-only-jwt-secret-change-me` — MUST override in prod) — Phase 13.2 (LIVE)
- `IVE_AUTH_JWT_ALGORITHM` (default `HS256`) — Phase 13.2 (LIVE)
- `IVE_AUTH_JWT_TTL_SECONDS` (default `3600` — 1h access token) — Phase 13.2 (LIVE)
- `IVE_AUTH_REFRESH_TTL_SECONDS` (default 14d) — Phase 13.2 (LIVE)
- `IVE_AUTH_REFRESH_COOKIE_NAME` (default `ive_refresh`) — Phase 13.2 (LIVE)
- `IVE_AUTH_REFRESH_COOKIE_SECURE` (default `False`; flip True behind Traefik HTTPS in M14) — Phase 13.2 (LIVE)

### 6.3 Ports

| Service | Port | Reason |
|---|---|---|
| `auto-inspect-edge` | 8000 | existing |
| `auto-inspect-service` | 8001 | existing |
| **`indusia-visual-editor` (us)** | **8002** | next free slot |
| Ollama | 11434 | upstream default |
| Postgres (dev container) | **5433** (host) → 5432 (container) | 5432 stays free for native Postgres |
| Vue dev server | 5173 | Vite default |

### 6.4 Async patterns

- All FastAPI route handlers are `async def`
- All DB calls go through `AsyncSession` + `get_session` dependency
- All external HTTP calls use `httpx.AsyncClient`
- Subprocess calls use `asyncio.subprocess` if invoked from a route, never blocking `subprocess.run`

### 6.5 Logging (M14.4 — structlog)

```python
from indusia_visual_editor.utils.logging_config import get_logger, bind_context, clear_context
logger = get_logger(__name__)
```

Never `import logging` for new module loggers. `get_logger` returns a `structlog.BoundLogger` that auto-merges contextvars (e.g. `request_id`) into every record. Stdlib `%-formatting` still works (`logger.info("trained %s", run_id)`) because `make_filtering_bound_logger` interpolates `*args` into the event string.

Add ad-hoc context with `bind_context(key=val)` — automatically scoped to the current async task; `clear_context()` drops all bound vars (request middleware already does this on response).

Renderer mode controlled by `IVE_LOG_MODE` (`prod` → JSON, `dev` → console). Default `prod`.

### 6.5b Tracing (M14.5 — OpenTelemetry)

```python
from indusia_visual_editor.utils.otel_config import get_tracer
_tracer = get_tracer(__name__)

with _tracer.start_as_current_span("ollama.generate", attributes={"llm.model": "gemma4:31b"}):
    ...
```

Use for non-trivial outbound calls (HTTP, subprocess, ais CLI). FastAPI inbound spans and httpx outbound spans are auto-instrumented in `main.py`, so don't double-wrap them. When in async generators, use `start_span` + try/finally/`span.end()` instead of `with` — async-generator yields don't compose cleanly with context managers.

Spans are no-op when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset (dev default) — safe to leave the lines in.

### 6.6 Error handling

All LLM / external-service calls raise typed exceptions:
- `LlmError` — Ollama timeout, JSON parse, validation
- `InspectServiceError` — auto-inspect-service HTTP failure
- `AssetError` — BOM parse, image, storage
- `BomParseError` — specific BOM parse failures (Bahasa Indonesia error messages)

Map these to HTTP responses via FastAPI exception handlers in `main.py`. Mirror `auto-inspect-service` pattern.

### 6.7 Testing

- `tests/` mirrors `src/` structure: `tests/routes/`, `tests/services/`, etc.
- `pytest-asyncio` mode = `auto`, so async tests don't need explicit `@pytest.mark.asyncio`
- HTTP tests use `httpx.AsyncClient` + `ASGITransport(app=app)` — do NOT use `TestClient` (sync)
- DB tests use a separate test DB + transactional rollback fixture (set up in Phase 1.1)
- Fixtures for BOMs / images go in `tests/fixtures/`

## 7. Database schema — migrations 0001–0011 LIVE

Live migrations: `0001_initial_schema` (`projects`, `assets`, `bom_items`), `0002_proposed_pipelines`, `0003_adapt_runs`, `0004_pre_labels`, `0005_labels`, `0006_bom_items_detector_presets` (adds `scope_mode` + `detector_presets` columns to `bom_items`), `0007_train_runs`, `0008_deployments`, `0009_edges`, `0010_chat_sessions`, `0011_auth` (adds `organizations`, `users` with role CHECK admin/engineer/viewer + email UNIQUE + bcrypt password_hash, and nullable `projects.organization_id` FK CASCADE; seeds default org `00000000-...-0001` + back-fills existing projects).

```sql
-- Phase 1.1
projects (
  id UUID PK,
  name TEXT,
  slug TEXT UNIQUE,
  status TEXT CHECK (status IN ('drafting','training','deployed','failed')),
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

assets (
  id UUID PK,
  project_id UUID FK → projects,
  kind TEXT CHECK (kind IN ('bom','golden_top','golden_bottom','drawing')),
  path TEXT,        -- relative to IVE_STORAGE_ROOT
  sha256 TEXT,      -- for dedup
  mime TEXT,
  size_bytes BIGINT,
  uploaded_at TIMESTAMPTZ
)

bom_items (
  id UUID PK,
  project_id UUID FK,
  designator TEXT,         -- e.g. "R1"
  value TEXT,              -- e.g. "10kΩ"
  package TEXT,            -- e.g. "0805"
  qty INT,
  position_hint TEXT,
  -- scope (user-controlled in canvas)
  inspect_scope TEXT CHECK (inspect_scope IN ('pending','inspected','skipped')) DEFAULT 'pending',
  mi_likely BOOL,
  component_type TEXT,     -- 'electrolytic_cap','dip_ic','connector','tht_resistor','smd_generic',...
  defect_history_count INT DEFAULT 0,
  -- M6 Phase 6.6 columns (migration 0006)
  scope_mode TEXT CHECK (scope_mode IN ('per_component','whole_side')) DEFAULT 'per_component',
  detector_presets JSONB,  -- list[str] of names from data/defect_detector_mapping.yaml
  extra JSONB              -- preserved BOM columns we don't model
)

-- Phase 3.4+
proposed_pipelines (
  id UUID PK, project_id UUID FK, version INT, dag_json JSONB,
  approved_by UUID, approved_at TIMESTAMPTZ
)

-- M6 LIVE (migration 0005)
labels (
  id UUID PK, project_id UUID FK ON DELETE CASCADE,
  side TEXT CHECK (side IN ('top','bottom')),
  version INT,
  ls_json JSONB,           -- exact LS-JSON shape from LSF onSubmit
  snapshot_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(project_id, side, version)
)

-- M7 LIVE (migration 0007)
train_runs (
  id UUID PK, project_id UUID FK ON DELETE CASCADE,
  adapt_run_id UUID FK ON DELETE CASCADE,    -- lineage: which graphflow tree was trained
  service_job_id TEXT,                       -- auto-inspect-service handle for SSE re-attach
  status TEXT CHECK (status IN ('pending','running','succeeded','failed','cancelled')),
  metrics_json JSONB,                        -- includes per-component F1, not just global mAP
  started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ,
  error_text TEXT,
  INDEX (project_id), INDEX (service_job_id)
)

-- M10
deployments (
  id UUID PK, project_id UUID FK, train_run_id UUID FK,
  model_version TEXT, edges_notified JSONB, deployed_at TIMESTAMPTZ
)

-- M12
chat_sessions (id UUID PK, project_id UUID FK, messages_json JSONB, created_at TIMESTAMPTZ)
```

UUID PKs, timezone-aware timestamps, FKs with `ON DELETE CASCADE` only when explicitly justified.

## 8. Domain glossary — DO NOT MISUSE

| Term | Meaning | Common confusion |
|---|---|---|
| **PCB** | Printed Circuit Board | not "PCBA"; the bare board |
| **SMT** | Surface Mount Technology — auto pick-and-place, AOI machine handles inspection | EXISTING AOI covers this; we do NOT replace it |
| **MI** | Manual Insertion — through-hole + wave solder, **no inspection automation today** | **OUR PRIMARY TARGET** |
| **AOI** | Automated Optical Inspection (machine on SMT line) | sibling to us; we are AOI-equivalent for MI |
| **BOM** | Bill of Materials, 200-400 rows | NOT the same as inspect-list (5-50 rows) |
| **inspect-list** | subset of BOM the operator chose to inspect | derived from canvas annotation, not BOM directly |
| **designator** | per-component label like `R1`, `C4`, `U7` | regex `^[A-Z]+[0-9]+$`; multi-designator BOM rows (`R1, R2, R3`) expand to 3 rows |
| **golden sample** | photograph of a known-good PCB (top + bottom sides) | reference for training |
| **drawing** | PCB layout drawing (JPG/PNG only in v1; no Gerber/ODB++) | spatial prior for pre-label |
| **fiducial** | alignment mark on PCB (usually 3 corners) | tracked as `KeyPointLabels` in LSF |
| **graphflow DAG** | node-graph pipeline config in `auto-inspect-service` | per-PCB `config.yaml` + `components/*.yaml` |
| **Gate 1** | HITL approval before training starts | hard stop; user clicks "Start Training" |
| **Gate 2** | HITL approval before pushing weights to edges | hard stop; user clicks "Promote to Production" |

### Defect criteria (user picks per-region in canvas)

`missing_component`, `orientation`, `polarity_flip`, `connector_pin_bending`, `missing_pin_connector`, `lifted_pin`, `wrong_value`, `misalignment`, `solder_short` (whole-side mode only).

Mapping criterion → detector preset lives in `data/defect_detector_mapping.yaml` (Phase 2.2c). Single source of truth.

## 9. LLM — Gemma 4 (Ollama)

### 9.1 The four roles

| Role | Trigger | Phase | Output schema |
|---|---|---|---|
| Pipeline planner | user clicks "🤖 Build inspection pipeline" after labeling | M4 | `ProposedPipeline` |
| Pre-label assistant | user opens LabelingCanvas with no annotations yet | M5 | `list[PreLabeledRegion]` |
| Runtime defect judge | edge sends ROI crop for borderline cases | **v1.5 (NOT in MVP)** | `DefectVerdict` |
| Training/diagnostics advisor | user opens chat drawer | M12 | `ChatTurn` (streamed) |

### 9.2 Structured output contract

ALL Gemma calls use `format=json` + pydantic validation. Never trust raw text. Schemas live in `services/llm/schemas.py`. If validation fails, raise `LlmError`, never accept the malformed output.

```python
class ProposedPipelineStep(BaseModel):
    designator: str                    # regex ^[A-Z]+[0-9]+$
    component_type: str
    detectors: list[Literal["yolo","anomalib","ocr","barcode","template_match"]]
    reasoning: str

class ProposedPipeline(BaseModel):
    pcb_model: str
    fiducial_strategy: Literal["circle","orb","yolo","threshold"]
    steps: list[ProposedPipelineStep]

class PreLabeledRegion(BaseModel):
    designator: str
    bbox: tuple[float, float, float, float]  # x, y, w, h normalized 0-1
    confidence: float
    side: Literal["top","bottom"]

class DefectVerdict(BaseModel):
    verdict: Literal["pass","fail","uncertain"]
    confidence: float
    reason_short: str
    reason_detail: str
```

### 9.3 Performance budget (acceptance criteria)

| Call | Target | Notes |
|---|---|---|
| Planner | ≤30s | full BOM + golden image multi-MB |
| Pre-label | ≤60s | golden + drawing + BOM list |
| Judge | ≤2s | per ROI, runtime hot path — v1.5 only |
| Advisor | streaming, first token <3s | UX requirement |

## 10. LSF integration — boundary

LSF is a **third-party Apache-2.0 library** we vendor as a built artifact at `web/public/lsf/`. We DO NOT modify upstream LSF code. We DO NOT adopt Label Studio's Django backend, datamanager, UI library, schema, RBAC, or storage adapters.

### What we use
- `window.LabelStudio` class instantiated on a div in `LSFEmbed.vue` (React island in Vue 3)
- Declarative XML labeling config (composed per PCB from BOM + Gemma plan)
- Native LS-JSON output (zero adapter for storage; YOLO export is custom)
- ML Backend protocol — **deferred to v1.5** (v1 bakes predictions into task JSON)

### What we replace
- Dashboard, project wizard, BOM parser, planner UI, train/eval/deploy views, chat — all bespoke Vue 3 in our app

### Vendor commands
See `docs/specs/lsf-build.md`. Production build is `MODE=standalone yarn nx run editor:build:production` (NOT the spec's outdated `yarn lsf:build`). Output dir is `web/dist/libs/editor/` (NOT `web/libs/editor/dist/`). Vendor the ENTIRE tree (chunks, WASM, fonts) minus maps and demo media.

### Loading in our HTML
```html
<link rel="stylesheet" href="/lsf/main.css">
<script type="module" src="/lsf/main.js"></script>
```

After load: `window.LabelStudio` is a function. `instanceOptions.reactVersion: 'v18'` required.

## 11. Two HITL gates — hard stops

| Gate | When | UI requirement |
|---|---|---|
| **Gate 1** | Before `auto-inspect-service /api/training/start` is called | Preview: dataset stats, AI-suggested epochs/augmentation. User must click "Start Training" button. |
| **Gate 2** | Before `ais model push` (promote weights to production registry) | Preview: eval metrics (mAP, per-component F1), sample predictions. User must click "Promote to Production" button. |

Never auto-approve. No "auto-continue if metrics > threshold" in v1.

## 12. Anti-AI-slop rules

Code, commit messages, UI strings, and docs.

| Forbidden | Use instead |
|---|---|
| "leverage", "synergies", "paradigm shift", "revolutionary", "game-changer" | concrete verbs and nouns |
| emoji as icons (UI) | Lucide React icons, 1.5px stroke |
| emoji in code (`# 🚀 deploy`) | plain comment if needed at all |
| "TODO", "FIXME", "placeholder", "dummy", "mock" left in shipped code | resolve or ask user before commit |
| corporate hype ("game-changing AI") | factual description |
| `console.log` left in JS | `if (import.meta.env.DEV) console.debug(...)` |
| Bahasa "Inggris-tinggi" like "sinergi", "leverage", "revolusi" in UI copy | "kerja sama", "manfaatkan", concrete verbs |
| commit message starting with "Update" or "Fix stuff" | imperative + scope: `feat(bom): parse Excel with multi-designator expansion` |

UI default language: **Bahasa Indonesia**, technical terms English. No emoji in UI strings. No translation of designators / component names / field names / API identifiers.

## 13. Path conventions

- **Windows backslash** for filesystem paths in code comments and docs (Ali's machine)
- **Forward slash** for URLs, S3 keys, Git paths
- All env paths normalized via `pathlib.Path` in Python code; never string-concat paths
- Storage layout: `storage/{project_id}/{kind}/{sha256}.{ext}` (see Phase 1.3)

## 13.5. Git workflow — solo-developer policy (LOCKED)

This is a single-maintainer project. The repo's `main` branch is the working trunk; there is **no PR review ceremony** unless the operator explicitly asks for one.

| Rule | Detail |
|---|---|
| **Default target** | Push directly to `origin/main` after each green phase. Do NOT open a PR by default. |
| **No new branches** (LOCKED 2026-05-26) | The agent MUST NOT create new branches under any circumstance, including `feat/*`, `fix/*`, `docs/*`, or hotfix branches. ALL changes — features, fixes, refactors, docs, experiments — commit + push directly to `main`. Historical M0–M14 saw orphaned `feat/m0-m1-m2-bootstrap-bom-pipeline` + `docs/m4-plan-breakdown` branches that had to be hand-cleaned; this rule prevents the regression. Only the operator may create a branch by hand if they explicitly ask for one. |
| **When to branch** | Only on explicit operator request (e.g. "buat PR dulu", "branch this"). Risk arguments (force-push, history rewrite, schema-destructive migration) DO NOT auto-trigger a branch — surface the risk, get explicit operator approval, and only then branch. |
| **Commit hygiene** | One conventional commit per phase, with the gaspol-execute Co-Authored-By trailer. Atomic — green tests before commit, never partial state. |
| **Pushing** | `git push origin main` is the standard end-of-phase action. Auto-mode classifier may still block this on first invocation; the operator pre-authorizes by adding `Bash(git push origin main:*)` to `.claude/settings.local.json`. Until that whitelist lands, the fallback is: operator runs the push manually from PowerShell, or merges a thin PR via the GitHub UI. |
| **Self-modification** | The agent is NOT allowed to edit `.claude/settings.local.json` itself — that's a high-trust action reserved for the operator. The agent surfaces the exact snippet to paste and waits. |
| **Hooks / signing** | Never `--no-verify`, never bypass GPG signing. If a hook fails, fix the underlying issue. |
| **PR scope** | If a PR IS opened, scope it to the milestone (e.g. "M0–M3") or the phase. Update title + body when scope changes. |

To pre-authorize main-pushes for future sessions: the operator (not the agent) adds two Bash patterns to the `permissions.allow` array in `.claude/settings.local.json` — one for `git push origin main` and one with the trailing wildcard variant. The agent does not edit this file, only references that the operator has applied this setting.

## 14. Build, test, run — current commands

```powershell
# One-time setup
$env:PATH = "$env:PATH;C:\Users\alisa\.local\bin"   # add poetry to PATH
Set-Location D:\Projects\indusia-visual-editor
poetry install

# Run tests
poetry run pytest -v

# Boot service (Phase 0.1+; reloads on src/ changes when --reload added)
poetry run uvicorn indusia_visual_editor.main:app --host 0.0.0.0 --port 8002

# Smoke /health
Invoke-WebRequest http://127.0.0.1:8002/health -UseBasicParsing
```

## 15. Reference paths (DO NOT hardcode in code — only in docs/scripts)

| What | Path |
|---|---|
| Existing inspection stack | `D:\Projects\Indusia-Inspection\` |
| auto-inspect-service configs | `D:\Projects\Indusia-Inspection\auto-inspect-service\prod\configs\{pcb_id}\` |
| Label Studio upstream repo (LSF source) | `D:\Projects\label-studio\` |
| LSF built artifact | `D:\Projects\label-studio\web\dist\libs\editor\` (re-build via §10) |
| This project | `D:\Projects\indusia-visual-editor\` |
| User's Obsidian vault | `D:\Obsidian-Vault\` (decision log + cross-project memory) |

## 16. What NOT to do — top anti-hallucination guardrails

1. **Do not invent hooks, components, or routes.** Check the actual file tree first. As of 2026-05-26 (M14 close) the live routes are: `/health`, `/api/auth/signup` POST, `/api/auth/login` POST, `/api/auth/refresh` POST, `/api/auth/logout` POST, `/api/auth/me` GET, `/api/dashboard/summary` GET (public cross-project rollup — the ONLY backend addition from the 2026-05-30 Figma 100% FE redo; `services/dashboard/summary.py` + `routes/dashboard.py`), `/api/projects` CRUD (POST/PUT admin+engineer, DELETE admin-only — bearer-gated), `/api/projects/{id}/assets` (POST + GET list + binary), `/api/projects/{id}/bom_items` GET, `/api/projects/{id}/llm/plan` POST + GET, `/api/projects/{id}/llm/prelabel` POST + GET, `/api/projects/{id}/adapt` POST + GET, `/api/projects/{id}/labels/task` GET, `/api/projects/{id}/labels` POST + GET, `/api/projects/{id}/training/start` POST, `/api/projects/{id}/training/suggest-hyperparams` POST, `/api/projects/{id}/training` GET, `/api/training/{run_id}/stream` GET (SSE), `/api/training/{run_id}/eval` GET, `/api/projects/{id}/dataset/stats` GET, `/api/projects/{id}/deploy` POST + GET, `/api/edges` POST + GET, `/api/edges/{id}` PUT, `/api/edges/{id}/pin` PUT, `/api/projects/{id}/chat` POST + GET, `/api/chat/{session_id}` GET, `/api/chat/{session_id}/stream` POST (SSE), `/api/projects/{id}/inspection-feedback` POST (multipart ingest + optional ROI crop field `file`) + GET (?status= project list), `/api/inspection-feedback` GET (cross-project inbox — powers the global `/feedback` screen), `/api/inspection-feedback/{fid}` PUT (curate mark/status), `/api/inspection-feedback/{fid}/promote` POST (escape→DefectExample; the inspection-logic gate rejects overkill / missing-ROI / invalid-criterion / already-promoted with 409) — the v1 inspection-feedback loop shipped 2026-05-30 (`routes/inspection_feedback.py` + `services/feedback/roi_store.py` writing `{pid}/feedback_roi/{sha}{ext}`; live edge-push stays v1.5, ingest is fed manually/by script). Every POST/PUT/DELETE outside `/api/auth/*` requires `Authorization: Bearer <access_token>` (Phase 13.3); GETs stay public in v1 (DECISION POINT — viewer role uses them without auth).
2. **Tables live as of M14 close**: `projects` (with `organization_id` FK CASCADE from migration 0011), `assets`, `bom_items` (with `scope_mode` + `detector_presets` from migration 0006), `proposed_pipelines`, `adapt_runs`, `pre_labels`, `labels`, `train_runs`, `deployments`, `edges`, `chat_sessions`, `organizations`, `users`, `inspection_feedback` (model_verdict/operator_mark/status + nullable ROI crop path/sha + edge_id/train_run_id SET-NULL FKs) + `defect_examples` (promoted escape → training sample; criterion + ROI NOT NULL) — via migrations 0001–**0012** (`0012_inspection_feedback`, down_revision `0011_auth`). Seed organization at id `00000000-0000-0000-0000-000000000001` slug=`default` is provisioned by 0011_auth so v1 single-tenant signups always land in a real org.
3. **Do not modify `D:\Projects\Indusia-Inspection\` or `D:\Projects\label-studio\`** from this project. They are sibling repos with their own lifecycle.
4. **Do not fork LSF.** We vendor the built artifact; no source-level changes.
5. **Do not substitute mock data for real integrations.** If a hook / service / table doesn't exist, raise it as a blocker and ask. See gaspol-execute Iron Laws.
6. **Do not commit secrets.** `.env` is gitignored; only `.env.example` is committed.
7. **Do not change Python version requirements** without flagging — `requires-python = ">=3.10,<4.0"` is locked.
8. **Do not use sync `requests` or `psycopg2`** in route handlers. Async-first stack.
9. **Do not skip TDD gate** in plan phases. Every phase step 1 is "Write failing test". If a phase plan doesn't have it, raise it as a plan template violation.
10. **Do not skip CLAUDE.md.** Read this file every session start. Update it when shipping new routes / hooks / tables / conventions.
11. **Do not `import logging` for new module loggers.** Use `from indusia_visual_editor.utils.logging_config import get_logger; logger = get_logger(__name__)` (M14.4). Stdlib `logging.getLogger(__name__)` bypasses the structlog renderer + request_id contextvar binding and produces unstructured stderr lines that the log aggregator can't index.
12. **Do not double-wrap outbound HTTP / FastAPI spans.** `FastAPIInstrumentor` + `HTTPXClientInstrumentor` are wired in `main.py` (M14.5) and emit spans automatically. Manual `tracer.start_as_current_span` is for app-level semantics (model name, phase, fan-out counts) — not for re-tracing what auto-instrumentation already covers.
13. **Do not invent FE routes, views, or stores.** As of 2026-05-27 (F0–F6 close) the live FE routes are: `/login` + `/signup` (meta.public), `/` Dashboard, `/projects/new` → redirect, `/projects/:id/wizard`, `/projects/:id/labeling`, `/projects/:id/gate1`, `/projects/:id/training/:runId`, `/projects/:id/setup-eval/:runId`, `/projects/:id/eval/:runId`, `/projects/:id/eval/:runId/gate2`, `/models`, `/edges`, `/datasets`, `/team`, `/preferences`, `/feedback` (cross-project inspection-feedback inbox, S7 — added 2026-05-30, WORKSPACE nav item in `AppSidebar.vue`). Live Pinia stores are exactly: `useAuthStore`, `useProjectsStore`, `useWizardStore`, `useLabelsStore`, `useTrainingStore`, `useEvalStore`, `useDeployStore`, `useEdgesStore`, `useChatStore`, `useToastStore`, `useUiStore`, `useEngineerStore`, `useInspectionFeedbackStore`. Live views: LoginView, SignupView, DashboardView, WizardView, LabelingView, Gate1View, TrainingView, SetupEvalView, EvalView, Gate2View, ModelsView, EdgesView, DatasetsView, TeamView, PreferencesView, InspectionFeedbackView, NotFoundView. FE feedback wiring: `api/inspectionFeedback.ts` (ROI uploaded under FormData field `file` to match the backend param). **Always grep `web/src/router/index.ts` + `web/src/stores/` before claiming a route/store exists.**
14. **Do not use EventSource for POST-body SSE.** `EventSource` cannot POST a body — for `POST /api/chat/{session_id}/stream` the FE uses `fetch()` + `ReadableStream` manually parsed in `api/chat.ts streamReply()` async generator. Same pattern applies if any future SSE endpoint requires a request body.
15. **Threshold logic lives client-side in `api/eval.ts`.** `EVAL_THRESHOLDS` (mAP 0.80 / F1 macro 0.80 / per-component F1 0.70) and `classifyEval(metrics, hasCorrections)` are exported from the FE — backend doesn't compute verdicts. If you change thresholds, change this one file (and the M15 backend `project_thresholds` table when shipped).
16. **Inspection-domain work MUST consult the `ai-visual-inspection-expert` skill FIRST — before acting.** This is a hard checkpoint, not a suggestion. Any task that touches the inspection domain — choosing an AI model/detector for a defect, picking `detector_presets` / `scope_mode` / fiducial strategy, judging defect-vs-acceptable (IPC-A-610 Class 1/2/3), imaging/lighting decisions, MI/THT & per-package defect calls, training-data strategy, eval thresholds, or Gate 1 / Gate 2 reasoning — STOP and invoke the project skill at `.claude/skills/ai-visual-inspection-expert/` (SKILL.md + its `references/`) to **validate that the planned steps are correct** before writing code, proposing a pipeline, or giving a verdict. Treat the skill as the senior engineer you check your plan against; state what it confirmed or corrected. The skill is a NotebookLM-research-backed Senior AI Visual Inspection Engineer (EMS/PCB; phone/camera/medical) over 400+ cited sources. Do NOT improvise inspection guidance from training memory when this skill applies — if a figure isn't in the skill's references, say so rather than invent.

## 17. Update protocol for this file

When a phase ships new artifacts, append to the relevant section here in the same PR/commit. Example:

- Phase 1.1 ships → update §7 ("Built" column for `projects/assets/bom_items` tables) and §16 ("DB schema exists; check migrations" instead of "no tables")
- Phase 0.3 ships → update §2 (frontend status), add §5b (frontend file layout), update §14 (frontend dev commands)
- Adoption-spec corrections → propagate to §10 (LSF integration boundary)

This file is the single source of truth for "what is true now". If reality diverges, fix this file BEFORE writing more code.
