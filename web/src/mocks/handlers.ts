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

const SAMPLE_PROJECTS = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    name: 'PCB-A12 Main Board',
    slug: 'pcb-a12-main',
    status: 'deployed' as const,
    organization_id: SAMPLE_USER.organization_id,
    created_at: '2026-04-12T03:11:00Z',
    updated_at: '2026-05-25T08:42:00Z',
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    name: 'PCB-B07 Driver Board',
    slug: 'pcb-b07-driver',
    status: 'training' as const,
    organization_id: SAMPLE_USER.organization_id,
    created_at: '2026-05-19T01:20:00Z',
    updated_at: '2026-05-27T02:14:00Z',
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    name: 'PCB-C03 Power Supply',
    slug: 'pcb-c03-psu',
    status: 'drafting' as const,
    organization_id: SAMPLE_USER.organization_id,
    created_at: '2026-05-26T05:33:00Z',
    updated_at: '2026-05-26T05:33:00Z',
  },
]

export const handlers = [
  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string }
    if (!body?.email || !body?.password) {
      return failed('email and password required', 422)
    }
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
    if (!body?.email || !body?.password) {
      return failed('email and password required', 422)
    }
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
  http.get('/api/projects', () => HttpResponse.json(envelope(SAMPLE_PROJECTS))),
  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as { name?: string; slug?: string }
    const now = new Date().toISOString()
    return HttpResponse.json(
      envelope(
        {
          id: crypto.randomUUID(),
          name: body.name ?? 'Untitled',
          slug: body.slug ?? 'untitled',
          status: 'drafting' as const,
          organization_id: SAMPLE_USER.organization_id,
          created_at: now,
          updated_at: now,
        },
        'project created',
      ),
      { status: 201 },
    )
  }),
]
