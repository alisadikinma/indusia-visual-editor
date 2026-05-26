import { http, HttpResponse } from 'msw'

const envelope = <T>(data: T, message = 'ok') => ({ status: true, message, data })

export const handlers = [
  http.get('/api/projects', () =>
    HttpResponse.json(envelope({ items: [], total: 0 })),
  ),
  http.post('/api/auth/login', () =>
    HttpResponse.json(
      envelope({
        access_token: 'mock-access-token',
        user: {
          id: '00000000-0000-0000-0000-000000000001',
          email: 'demo@indusia.example',
          role: 'admin',
          organization_id: '00000000-0000-0000-0000-000000000001',
        },
      }),
    ),
  ),
  http.get('/api/auth/me', () =>
    HttpResponse.json(
      envelope({
        id: '00000000-0000-0000-0000-000000000001',
        email: 'demo@indusia.example',
        role: 'admin',
        organization_id: '00000000-0000-0000-0000-000000000001',
      }),
    ),
  ),
]
