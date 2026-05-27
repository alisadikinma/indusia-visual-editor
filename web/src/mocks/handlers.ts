import { http, HttpResponse } from 'msw'

const envelope = <T>(data: T, message = 'ok') => ({ status: true, message, data })
const failed = (message: string, status = 400) =>
  HttpResponse.json({ status: false, message, data: null }, { status })

const SAMPLE_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'demo@indusia.example',
  role: 'admin' as const,
  organization_id: '00000000-0000-0000-0000-000000000001',
}

interface MockProject {
  id: string
  name: string
  slug: string
  status: 'drafting' | 'training' | 'deployed' | 'failed'
  organization_id: string
  created_at: string
  updated_at: string
}

const projectsDb: MockProject[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    name: 'PCB-A12 Main Board',
    slug: 'pcb-a12-main',
    status: 'deployed',
    organization_id: SAMPLE_USER.organization_id,
    created_at: '2026-04-12T03:11:00Z',
    updated_at: '2026-05-25T08:42:00Z',
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    name: 'PCB-B07 Driver Board',
    slug: 'pcb-b07-driver',
    status: 'training',
    organization_id: SAMPLE_USER.organization_id,
    created_at: '2026-05-19T01:20:00Z',
    updated_at: '2026-05-27T02:14:00Z',
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    name: 'PCB-C03 Power Supply',
    slug: 'pcb-c03-psu',
    status: 'drafting',
    organization_id: SAMPLE_USER.organization_id,
    created_at: '2026-05-26T05:33:00Z',
    updated_at: '2026-05-26T05:33:00Z',
  },
]

interface MockAsset {
  id: string
  project_id: string
  kind: 'bom' | 'golden_top' | 'golden_bottom' | 'drawing'
  path: string
  sha256: string
  mime: string | null
  size_bytes: number | null
  uploaded_at: string
}

const assetsDb = new Map<string, MockAsset[]>()

function sampleBom(projectId: string) {
  const rows = [
    { d: 'R1', v: '10kΩ', pkg: '0805', qty: 2, mi: false, ct: 'smd_generic' },
    { d: 'R2', v: '10kΩ', pkg: '0805', qty: 2, mi: false, ct: 'smd_generic' },
    { d: 'C1', v: '100nF', pkg: '0603', qty: 4, mi: false, ct: 'smd_generic' },
    { d: 'C4', v: '470uF/25V', pkg: 'THT-D10', qty: 1, mi: true, ct: 'electrolytic_cap' },
    { d: 'U1', v: 'STM32F103', pkg: 'LQFP-48', qty: 1, mi: false, ct: 'qfp' },
    { d: 'U7', v: 'ATmega328P', pkg: 'DIP-28', qty: 1, mi: true, ct: 'dip_ic' },
    { d: 'J1', v: 'USB-B', pkg: 'TH-USB-B', qty: 1, mi: true, ct: 'connector' },
    { d: 'J5', v: 'Header 2x10', pkg: 'TH-2.54mm', qty: 1, mi: true, ct: 'connector' },
    { d: 'D1', v: 'LED green', pkg: '0805', qty: 1, mi: false, ct: 'smd_generic' },
    { d: 'D2', v: '1N4148', pkg: 'SOD-323', qty: 2, mi: false, ct: 'smd_generic' },
  ]
  return rows.map((r) => ({
    id: crypto.randomUUID(),
    project_id: projectId,
    designator: r.d,
    value: r.v,
    package: r.pkg,
    qty: r.qty,
    position_hint: null,
    inspect_scope: 'pending' as const,
    mi_likely: r.mi,
    component_type: r.ct,
    defect_history_count: 0,
    extra: null,
  }))
}

const bomDb = new Map<string, ReturnType<typeof sampleBom>>()
bomDb.set(projectsDb[0].id, sampleBom(projectsDb[0].id))
bomDb.set(projectsDb[1].id, sampleBom(projectsDb[1].id))

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

interface MockTrainRun {
  id: string
  project_id: string
  adapt_run_id: string
  service_job_id: string
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  metrics_json: Record<string, unknown> | null
  started_at: string
  ended_at: string | null
  error_text: string | null
}

const trainRunsDb: MockTrainRun[] = []

interface MockEdge {
  id: string
  name: string
  webhook_url: string
  version_policy: {
    mode: 'auto_pull_latest' | 'pinned'
    pinned_model?: string
    pinned_version?: string
  }
  registered_at: string
  last_seen_at: string | null
}

const now = Date.now()
const edgesDb: MockEdge[] = [
  {
    id: 'edge-01',
    name: 'EDGE-01 · Line A',
    webhook_url: 'https://edge-01.factory.local/hook',
    version_policy: { mode: 'auto_pull_latest' },
    registered_at: '2026-04-01T01:00:00Z',
    last_seen_at: new Date(now - 30_000).toISOString(),
  },
  {
    id: 'edge-02',
    name: 'EDGE-02 · Line B',
    webhook_url: 'https://edge-02.factory.local/hook',
    version_policy: {
      mode: 'pinned',
      pinned_model: 'pcb-a12',
      pinned_version: 'v20260420-002',
    },
    registered_at: '2026-04-01T01:05:00Z',
    last_seen_at: new Date(now - 90_000).toISOString(),
  },
  {
    id: 'edge-03',
    name: 'EDGE-03 · Repair bay',
    webhook_url: 'https://edge-03.factory.local/hook',
    version_policy: { mode: 'auto_pull_latest' },
    registered_at: '2026-05-12T07:30:00Z',
    last_seen_at: new Date(now - 45_000).toISOString(),
  },
  {
    id: 'edge-04',
    name: 'EDGE-04 · Sample QA',
    webhook_url: 'https://edge-04.factory.local/hook',
    version_policy: { mode: 'auto_pull_latest' },
    registered_at: '2026-05-20T03:11:00Z',
    last_seen_at: null,
  },
]

const modelsDb = [
  {
    id: 'm-1',
    project_name: 'PCB-A12 Main Board',
    pcb_name: 'pcb-a12',
    version: 'v20260525-3f01',
    sha256: 'b3f9c1a7e4d2bc88aabb1234efcd567890aabbccddeeff00112233445566778899',
    size_mb: 184,
    promoted_at: '2026-05-25T08:42:00Z',
    pinned_edges: 1,
    status: 'production' as const,
  },
  {
    id: 'm-2',
    project_name: 'PCB-A12 Main Board',
    pcb_name: 'pcb-a12',
    version: 'v20260420-002',
    sha256: 'a1b2c3d4e5f6789012345678abcdef0123456789aabbccddeeff00112233445566',
    size_mb: 182,
    promoted_at: '2026-04-20T10:05:00Z',
    pinned_edges: 1,
    status: 'archived' as const,
  },
  {
    id: 'm-3',
    project_name: 'PCB-B07 Driver Board',
    pcb_name: 'pcb-b07',
    version: 'v20260527-stage',
    sha256: 'c4d5e6f7a8b9012345678901234567890abcdef0123456789aabbccddeeff0011',
    size_mb: 176,
    promoted_at: '2026-05-27T02:30:00Z',
    pinned_edges: 0,
    status: 'staged' as const,
  },
]

const datasetsDb = [
  {
    id: 'd-1',
    name: 'pcb-a12-train-v3',
    project: 'pcb-a12-main',
    region_count: 1840,
    size_mb: 612,
    created_at: '2026-05-22T09:00:00Z',
    kind: 'training' as const,
  },
  {
    id: 'd-2',
    name: 'pcb-a12-holdout-v3',
    project: 'pcb-a12-main',
    region_count: 142,
    size_mb: 48,
    created_at: '2026-05-22T09:01:00Z',
    kind: 'holdout' as const,
  },
  {
    id: 'd-3',
    name: 'edge-prod-24h-2026-05-26',
    project: 'pcb-a12-main',
    region_count: 24,
    size_mb: 6,
    created_at: '2026-05-26T23:00:00Z',
    kind: 'production_run' as const,
  },
  {
    id: 'd-4',
    name: 'pcb-b07-train-v1',
    project: 'pcb-b07-driver',
    region_count: 920,
    size_mb: 304,
    created_at: '2026-05-19T01:30:00Z',
    kind: 'training' as const,
  },
]

const teamDb = [
  {
    id: 't-1',
    email: 'demo@indusia.example',
    role: 'admin' as const,
    last_active_at: new Date().toISOString(),
    created_at: '2026-03-01T00:00:00Z',
  },
  {
    id: 't-2',
    email: 'engineer@indusia.example',
    role: 'engineer' as const,
    last_active_at: new Date(now - 60 * 60_000).toISOString(),
    created_at: '2026-03-15T00:00:00Z',
  },
  {
    id: 't-3',
    email: 'viewer@indusia.example',
    role: 'viewer' as const,
    last_active_at: new Date(now - 24 * 60 * 60_000).toISOString(),
    created_at: '2026-04-12T00:00:00Z',
  },
]

interface MockChatSession {
  id: string
  project_id: string
  messages_json: Array<{ role: 'user' | 'assistant' | 'system'; content: string; ts: string }>
  created_at: string
  updated_at: string
}
const chatDb: MockChatSession[] = []

function sampleStats() {
  const designators = ['R1', 'R2', 'C1', 'C4', 'U1', 'U7', 'J1', 'J5', 'D1', 'D2']
  const per = designators.map((d, i) => {
    const count = 18 + (i % 4) * 6
    const bucket = count >= 30 ? 'sufficient' : count >= 18 ? 'moderate' : 'at_risk'
    return { designator: d, count, bucket: bucket as 'sufficient' | 'moderate' | 'at_risk' }
  })
  return {
    total_regions: per.reduce((a, p) => a + p.count, 0),
    per_designator: per,
    coverage_ratio: 0.95,
    side_breakdown: { top: per.length * 8, bottom: per.length * 4 },
  }
}

function sampleEval(runId: string) {
  const designators = ['R1', 'R2', 'C1', 'C4', 'U1', 'U7', 'J1', 'J5', 'D1', 'D2']
  const per_component = designators.map((d, i) => {
    // J5 fails per spec example
    const f1 = d === 'J5' ? 0.63 : 0.78 + (i % 3) * 0.04
    const precision = f1 + 0.02
    const recall = f1 - 0.02
    return {
      designator: d,
      f1,
      precision,
      recall,
      support: 12 + (i % 3) * 4,
      pass: f1 >= 0.7,
    }
  })
  const predictions = designators.flatMap((d, i) => {
    const status = i % 4 === 0 ? 'fp' : i % 5 === 0 ? 'fn' : 'tp'
    return [
      {
        id: `pred-${d}-${i}`,
        designator: d,
        status: status as 'tp' | 'fp' | 'fn' | 'tn',
        confidence: 0.65 + (i % 4) * 0.1,
        thumbnail_url: null,
      },
    ]
  })
  return {
    run_id: runId,
    metrics: {
      map: 0.83,
      f1_macro: 0.78,
      precision_macro: 0.81,
      recall_macro: 0.75,
      per_component,
      false_positives: predictions.filter((p) => p.status === 'fp').length,
      false_negatives: predictions.filter((p) => p.status === 'fn').length,
    },
    predictions,
    prev_metrics: null,
  }
}

export const handlers = [
  // ───── auth ─────
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string }
    if (!body?.email || !body?.password) return failed('email and password required', 422)
    return HttpResponse.json(
      envelope({
        access_token: 'mock-access-token',
        token_type: 'Bearer',
        expires_in: 3600,
        user: { ...SAMPLE_USER, email: body.email },
      }),
    )
  }),
  http.post('/api/auth/signup', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string }
    if (!body?.email || !body?.password) return failed('email and password required', 422)
    return HttpResponse.json(
      envelope(
        {
          access_token: 'mock-access-token',
          token_type: 'Bearer',
          expires_in: 3600,
          user: { ...SAMPLE_USER, email: body.email },
        },
        'account created',
      ),
      { status: 201 },
    )
  }),
  http.post('/api/auth/refresh', () =>
    HttpResponse.json(envelope({ access_token: 'mock-access-token-refreshed' })),
  ),
  http.post('/api/auth/logout', () => HttpResponse.json(envelope(null, 'logged out'))),
  http.get('/api/auth/me', () => HttpResponse.json(envelope(SAMPLE_USER))),

  // ───── projects ─────
  http.get('/api/projects', () => HttpResponse.json(envelope(projectsDb))),
  http.get('/api/projects/:id', ({ params }) => {
    const found = projectsDb.find((p) => p.id === params.id)
    if (!found) return failed('project not found', 404)
    return HttpResponse.json(envelope(found))
  }),
  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as { name?: string; slug?: string }
    if (!body?.name || !body?.slug) return failed('name and slug required', 422)
    if (projectsDb.some((p) => p.slug === body.slug))
      return failed('slug already exists', 409)
    const now = new Date().toISOString()
    const created: MockProject = {
      id: crypto.randomUUID(),
      name: body.name,
      slug: body.slug,
      status: 'drafting',
      organization_id: SAMPLE_USER.organization_id,
      created_at: now,
      updated_at: now,
    }
    projectsDb.unshift(created)
    return HttpResponse.json(envelope(created, 'project created'), { status: 201 })
  }),

  // ───── assets ─────
  http.post('/api/projects/:id/assets', async ({ request, params }) => {
    const projectId = String(params.id)
    if (!projectsDb.some((p) => p.id === projectId)) return failed('project not found', 404)
    const url = new URL(request.url)
    const kind = url.searchParams.get('kind') as MockAsset['kind'] | null
    if (!kind || !['bom', 'golden_top', 'golden_bottom', 'drawing'].includes(kind)) {
      return failed('invalid asset kind', 422)
    }
    const form = await request.formData()
    const file = form.get('file') as File | null
    if (!file) return failed('file required', 422)
    const buf = await file.arrayBuffer()
    const sha = Array.from(new Uint8Array(buf.slice(0, 8)))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('')
      .padEnd(64, '0')
    const asset: MockAsset = {
      id: crypto.randomUUID(),
      project_id: projectId,
      kind,
      path: `${projectId}/${kind}/${sha}.${file.name.split('.').pop() ?? 'bin'}`,
      sha256: sha,
      mime: file.type || null,
      size_bytes: file.size,
      uploaded_at: new Date().toISOString(),
    }
    const existing = assetsDb.get(projectId) ?? []
    assetsDb.set(projectId, [...existing.filter((a) => a.kind !== kind), asset])

    // Auto-parse BOM on upload to simulate backend pipeline
    if (kind === 'bom' && !bomDb.has(projectId)) {
      await delay(120)
      bomDb.set(projectId, sampleBom(projectId))
    }

    return HttpResponse.json(envelope(asset, 'asset uploaded'), { status: 201 })
  }),
  http.get('/api/projects/:id/assets', ({ params }) => {
    return HttpResponse.json(envelope(assetsDb.get(String(params.id)) ?? []))
  }),

  // ───── bom items ─────
  http.get('/api/projects/:id/bom_items', ({ params }) => {
    return HttpResponse.json(envelope(bomDb.get(String(params.id)) ?? []))
  }),

  // ───── labels ─────
  http.get('/api/projects/:id/labels/task', ({ params, request }) => {
    const projectId = String(params.id)
    const side = new URL(request.url).searchParams.get('side') ?? 'top'
    const rows = bomDb.get(projectId) ?? []
    if (rows.length === 0) return failed('project has no bom_items', 422)
    const designators = rows.map((r) => r.designator)
    const labelTags = designators
      .map((d) => `<Label value="${d}" background="#10b981" />`)
      .join('\n')
    const config = `<View>
  <Image name="image" value="$image" />
  <RectangleLabels name="region" toName="image">
${labelTags}
  </RectangleLabels>
</View>`
    // Build a sample prelabel: half the rows get a placeholder prediction
    const samplePredictions = designators.slice(0, 4).map((d, i) => ({
      id: `pred-${d}`,
      type: 'rectanglelabels',
      from_name: 'region',
      to_name: 'image',
      original_width: 1920,
      original_height: 1080,
      image_rotation: 0,
      value: {
        x: 10 + i * 18,
        y: 10 + i * 12,
        width: 8,
        height: 6,
        rotation: 0,
        rectanglelabels: [d],
      },
    }))
    return HttpResponse.json(
      envelope({
        config,
        task: {
          id: 1,
          data: {
            image:
              'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1920&q=80',
          },
          predictions: [
            {
              id: 1,
              model_version: 'gemma-4-prelabel',
              result: samplePredictions,
            },
          ],
          annotations: [],
        },
        side,
        designator_count: designators.length,
      }),
    )
  }),
  http.post('/api/projects/:id/labels', async ({ request, params }) => {
    const projectId = String(params.id)
    const side = new URL(request.url).searchParams.get('side') ?? 'top'
    const body = (await request.json()) as { ls_json?: unknown }
    if (!body?.ls_json) return failed('payload.ls_json missing', 422)
    return HttpResponse.json(
      envelope(
        {
          id: crypto.randomUUID(),
          project_id: projectId,
          side,
          version: 1,
          snapshot_at: new Date().toISOString(),
        },
        'labels saved',
      ),
      { status: 201 },
    )
  }),
  http.get('/api/projects/:id/labels', ({ params }) => {
    return HttpResponse.json(envelope([{ project_id: String(params.id), versions: [] }]))
  }),
  // ───── training ─────
  http.get('/api/projects/:id/dataset/stats', () => HttpResponse.json(envelope(sampleStats()))),
  http.post('/api/projects/:id/training/suggest-hyperparams', ({ params, request }) => {
    const projectId = String(params.id)
    const side = (new URL(request.url).searchParams.get('side') ?? 'top') as 'top' | 'bottom'
    return HttpResponse.json(
      envelope({
        project_id: projectId,
        side,
        stats: sampleStats(),
        hyperparameters: {
          epochs: 30,
          batch_size: 32,
          learning_rate: 0.001,
          augmentation_intensity: 'medium' as const,
          early_stopping_patience: 5,
          grounding_source: 'Gemma 4 · 31b · grounding 47 rows',
        },
      }),
    )
  }),
  http.post('/api/projects/:id/training/start', ({ params }) => {
    const projectId = String(params.id)
    const run = {
      id: crypto.randomUUID(),
      project_id: projectId,
      adapt_run_id: crypto.randomUUID(),
      service_job_id: 'svc-' + Math.random().toString(36).slice(2, 10),
      status: 'pending' as const,
      metrics_json: null,
      started_at: new Date().toISOString(),
      ended_at: null,
      error_text: null,
    }
    trainRunsDb.unshift(run)
    return HttpResponse.json(envelope(run, 'training started'), { status: 201 })
  }),
  http.get('/api/projects/:id/training', ({ params }) => {
    const projectId = String(params.id)
    return HttpResponse.json(
      envelope(trainRunsDb.filter((r) => r.project_id === projectId)),
    )
  }),

  // SSE: compose a quick scripted stream. EventSource hits this URL.
  http.get('/api/training/:runId/stream', ({ params }) => {
    const runId = String(params.runId)
    const encoder = new TextEncoder()
    const designators = ['R1', 'R2', 'C1', 'C4', 'U1', 'U7', 'J1', 'J5', 'D1', 'D2']
    const totalEpochs = 30

    const stream = new ReadableStream({
      async start(controller) {
        function send(payload: Record<string, unknown>) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`))
        }
        send({ event: 'running' })
        for (let epoch = 1; epoch <= totalEpochs; epoch++) {
          await delay(150)
          const perComp = designators.map((d, i) => {
            const ratio = epoch / totalEpochs
            const threshold = (i + 1) / designators.length
            const state = ratio >= threshold ? 'done' : ratio >= threshold - 0.1 ? 'training' : 'queued'
            return { designator: d, state }
          })
          send({
            event: 'epoch',
            epoch,
            total_epochs: totalEpochs,
            loss: 0.95 - epoch * 0.02,
            map: Math.min(0.95, 0.4 + epoch * 0.02),
            f1: Math.min(0.95, 0.42 + epoch * 0.018),
            precision: Math.min(0.95, 0.45 + epoch * 0.017),
            recall: Math.min(0.95, 0.4 + epoch * 0.019),
            eta_seconds: Math.max(0, (totalEpochs - epoch) * 24),
            gpu_mem_used_gb: 18.4,
            gpu_mem_total_gb: 24,
            log_line: `[epoch ${epoch}/${totalEpochs}] loss=${(0.95 - epoch * 0.02).toFixed(4)} mAP=${(0.4 + epoch * 0.02).toFixed(4)}`,
            per_component: perComp,
          })
        }
        await delay(150)
        send({
          event: 'succeeded',
          run_id: runId,
          metrics: { map: 0.87, f1_macro: 0.84 },
        })
        controller.close()
      },
    })
    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
  }),

  // ───── eval ─────
  http.get('/api/training/:runId/eval', ({ params }) => {
    const runId = String(params.runId)
    return HttpResponse.json(envelope(sampleEval(runId)))
  }),

  // ───── deploy ─────
  http.post('/api/projects/:id/deploy', ({ params }) => {
    const projectId = String(params.id)
    const now = new Date()
    const stamp = now.toISOString().replace(/[-:T]/g, '').slice(0, 14)
    const sha = Array.from({ length: 64 }, () =>
      Math.floor(Math.random() * 16).toString(16),
    ).join('')
    const deployment = {
      id: crypto.randomUUID(),
      project_id: projectId,
      train_run_id: trainRunsDb[0]?.id ?? crypto.randomUUID(),
      model_version: `v${stamp}-${projectId.slice(0, 6)}`,
      edges_notified: edgesDb.map((e) => ({
        edge_id: e.id,
        edge_name: e.name,
        ok: e.last_seen_at != null,
        status_code: e.last_seen_at != null ? 200 : null,
        error: e.last_seen_at != null ? null : 'edge unreachable',
      })),
      deployed_at: now.toISOString(),
      sha256: sha,
      registry_tag: `pcb-${projectId.slice(0, 6)}@v${stamp}`,
      push_command: `ais model push --pcb pcb-${projectId.slice(0, 6)} --tag v${stamp}`,
    }
    return HttpResponse.json(envelope(deployment, 'promoted to production'), { status: 201 })
  }),
  http.get('/api/projects/:id/deploy', () => HttpResponse.json(envelope([]))),

  // ───── edges ─────
  http.get('/api/edges', () => HttpResponse.json(envelope(edgesDb))),
  http.put('/api/edges/:id/pin', async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json()) as { model_name: string | null; version: string | null }
    const idx = edgesDb.findIndex((e) => e.id === id)
    if (idx === -1) return failed('edge not found', 404)
    const pin = body.model_name != null && body.version != null
    edgesDb[idx] = {
      ...edgesDb[idx],
      version_policy: pin
        ? {
            mode: 'pinned',
            pinned_model: body.model_name!,
            pinned_version: body.version!,
          }
        : { mode: 'auto_pull_latest' },
    }
    return HttpResponse.json(envelope(edgesDb[idx]))
  }),

  // ───── models / datasets / team (settings page mocks) ─────
  http.get('/api/models', () => HttpResponse.json(envelope(modelsDb))),
  http.get('/api/datasets', () => HttpResponse.json(envelope(datasetsDb))),
  http.get('/api/team', () => HttpResponse.json(envelope(teamDb))),

  // ───── chat (M12) ─────
  http.get('/api/projects/:id/chat', ({ params }) => {
    const projectId = String(params.id)
    const sessions = chatDb.filter((s) => s.project_id === projectId)
    return HttpResponse.json(envelope(sessions))
  }),
  http.post('/api/projects/:id/chat', ({ params }) => {
    const projectId = String(params.id)
    const session = {
      id: crypto.randomUUID(),
      project_id: projectId,
      messages_json: [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    chatDb.push(session)
    return HttpResponse.json(envelope(session, 'session created'), { status: 201 })
  }),
  http.get('/api/chat/:sessionId', ({ params }) => {
    const session = chatDb.find((s) => s.id === String(params.sessionId))
    if (!session) return failed('session not found', 404)
    return HttpResponse.json(envelope(session))
  }),
  http.post('/api/chat/:sessionId/stream', async ({ params, request }) => {
    const session = chatDb.find((s) => s.id === String(params.sessionId))
    if (!session) return failed('session not found', 404)
    const body = (await request.json()) as { user_message: string }
    const reply = `Berdasarkan run terakhir, ${body.user_message.slice(0, 60)}… — saya sarankan periksa per-component F1 dan tambah 5-10 sampel untuk komponen MI yang masih di bawah threshold 0.70.`
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      async start(controller) {
        const tokens = reply.split(' ')
        for (const token of tokens) {
          await delay(40)
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ delta: token + ' ' })}\n\n`),
          )
        }
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ event: 'done' })}\n\n`))
        controller.close()
      },
    })
    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
  }),

  http.post('/api/projects/:id/llm/prelabel', ({ params, request }) => {
    const projectId = String(params.id)
    const side = new URL(request.url).searchParams.get('side') ?? 'top'
    return HttpResponse.json(
      envelope(
        {
          id: crypto.randomUUID(),
          project_id: projectId,
          side,
          regions: [],
          created_at: new Date().toISOString(),
        },
        'prelabel scheduled',
      ),
      { status: 201 },
    )
  }),
]
