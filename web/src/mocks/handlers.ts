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
]
