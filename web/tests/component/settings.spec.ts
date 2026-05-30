import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import ModelsView from '@/views/ModelsView.vue'
import EdgesView from '@/views/EdgesView.vue'
import DatasetsView from '@/views/DatasetsView.vue'
import TeamView from '@/views/TeamView.vue'
import PreferencesView from '@/views/PreferencesView.vue'
import { server } from '@/mocks/server'
import { useUiStore } from '@/stores/ui'
import { useEngineerStore } from '@/stores/engineer'

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

async function mountView(C: unknown) {
  const wrapper = mount(C as never, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('Settings views', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('ModelsView renders the registry table and filters', async () => {
    server.use(
      http.get('*/api/models', () =>
        HttpResponse.json(env([
          { id: 'm1', project_name: 'Board A', pcb_name: 'pcb-a', version: 'v1', sha256: 'abcdef0123456789', size_mb: 184, promoted_at: '2026-05-25T00:00:00Z', pinned_edges: 1, status: 'production' },
        ])),
      ),
    )
    const w = await mountView(ModelsView)
    expect(w.get('[data-testid="models-table"]').text()).toContain('Board A')
  })

  it('EdgesView renders the registry with heartbeat + summary', async () => {
    server.use(
      http.get('*/api/edges', () =>
        HttpResponse.json(env([
          { id: 'e1', name: 'edge-01', webhook_url: 'https://e/h', version_policy: { mode: 'auto_pull_latest' }, registered_at: '', last_seen_at: new Date(Date.now() - 5000).toISOString() },
        ])),
      ),
    )
    const w = await mountView(EdgesView)
    expect(w.get('[data-testid="edges-table"]').text()).toContain('edge-01')
  })

  it('DatasetsView renders a card per dataset', async () => {
    server.use(
      http.get('*/api/datasets', () =>
        HttpResponse.json(env([
          { id: 'd1', name: 'set-a', project: 'pcb-a', region_count: 100, size_mb: 12, created_at: '2026-05-01T00:00:00Z', kind: 'training' },
          { id: 'd2', name: 'set-b', project: 'pcb-b', region_count: 50, size_mb: 6, created_at: '2026-05-02T00:00:00Z', kind: 'holdout' },
        ])),
      ),
    )
    const w = await mountView(DatasetsView)
    expect(w.findAll('[data-testid="dataset-card"]').length).toBe(2)
  })

  it('TeamView renders members with role badges', async () => {
    server.use(
      http.get('*/api/team', () =>
        HttpResponse.json(env([
          { id: 't1', email: 'admin@indusia.example', role: 'admin', last_active_at: null, created_at: '2026-03-01T00:00:00Z' },
        ])),
      ),
    )
    const w = await mountView(TeamView)
    expect(w.get('[data-testid="team-table"]').text().toLowerCase()).toContain('admin')
  })

  it('PreferencesView toggles locale, theme and engineer mode', async () => {
    const w = await mountView(PreferencesView)
    const ui = useUiStore()
    const eng = useEngineerStore()
    await w.get('[data-testid="preferences-theme-dark"]').trigger('click')
    expect(ui.theme).toBe('dark')
    await w.get('[data-testid="preferences-locale-id"]').trigger('change')
    expect(ui.locale).toBe('id')
    await w.get('[data-testid="preferences-engineer-toggle"]').trigger('click')
    expect(eng.enabled).toBe(true)
  })
})
