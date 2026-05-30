import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import DashboardView from '@/views/DashboardView.vue'
import { server } from '@/mocks/server'

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

const POPULATED = {
  stats: {
    active_projects: 12,
    drafting: 3,
    training: 2,
    deployed: 7,
    failed: 1,
    models_deployed: 8,
    edges_online: 5,
    edges_total: 6,
    avg_map: 0.913,
  },
  projects: [
    {
      id: 'p1',
      name: 'Mainboard XR-200',
      slug: 'mainboard-xr-200',
      status: 'deployed',
      updated_at: '2026-05-30T08:00:00Z',
      bom_count: 247,
      latest_map: 0.942,
    },
    {
      id: 'p2',
      name: 'Sensor Driver v2',
      slug: 'sensor-driver-v2',
      status: 'training',
      updated_at: '2026-05-30T07:00:00Z',
      bom_count: 89,
      latest_map: null,
    },
    {
      id: 'p3',
      name: 'Power Module A1',
      slug: 'power-module-a1',
      status: 'drafting',
      updated_at: '2026-05-30T06:00:00Z',
      bom_count: 132,
      latest_map: null,
    },
  ],
}

const EMPTY = {
  stats: {
    active_projects: 0,
    drafting: 0,
    training: 0,
    deployed: 0,
    failed: 0,
    models_deployed: 0,
    edges_online: 0,
    edges_total: 0,
    avg_map: null,
  },
  projects: [],
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: DashboardView },
      { path: '/projects/:id/wizard', name: 'wizard', component: { template: '<div>wiz</div>' } },
    ],
  })
}

async function mountDash(summary: unknown = POPULATED) {
  server.use(
    http.get('*/api/dashboard/summary', () => HttpResponse.json(env(summary))),
  )
  const router = makeRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(DashboardView, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

describe('DashboardView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the four stat cards from the summary endpoint', async () => {
    const { wrapper } = await mountDash()
    expect(wrapper.get('[data-testid="dashboard-stat-active"]').text()).toContain('12')
    expect(wrapper.get('[data-testid="dashboard-stat-models"]').text()).toContain('8')
    // edges online renders "X of Y"
    const edges = wrapper.get('[data-testid="dashboard-stat-edges"]').text()
    expect(edges).toContain('5')
    expect(edges).toContain('6')
    expect(wrapper.get('[data-testid="dashboard-stat-map"]').text()).toContain('0.913')
  })

  it('renders one featured hero plus the remaining project cards', async () => {
    const { wrapper } = await mountDash()
    const featured = wrapper.get('[data-testid="dashboard-featured"]')
    expect(featured.text()).toContain('Mainboard XR-200')
    expect(featured.text()).toContain('247')
    // remaining (non-featured) projects render as cards
    const cards = wrapper.findAll('[data-testid="dashboard-project-card"]')
    expect(cards).toHaveLength(2)
    expect(wrapper.text()).toContain('Sensor Driver v2')
    expect(wrapper.text()).toContain('Power Module A1')
  })

  it('does not fabricate trend deltas or the 7-day inspection chart', async () => {
    const { wrapper } = await mountDash()
    expect(wrapper.find('[data-testid="dashboard-chart"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="dashboard-trend"]').exists()).toBe(false)
    // no "inspected" telemetry surfaced (no inspection-results table backs it)
    expect(wrapper.text().toLowerCase()).not.toContain('inspected')
  })

  it('filter chips narrow the project list client-side', async () => {
    const { wrapper } = await mountDash()
    await wrapper.get('[data-testid="dashboard-filter-training"]').trigger('click')
    await flushPromises()
    const featured = wrapper.get('[data-testid="dashboard-featured"]')
    expect(featured.text()).toContain('Sensor Driver v2')
    expect(wrapper.findAll('[data-testid="dashboard-project-card"]')).toHaveLength(0)
  })

  it('shows the empty state when there are no projects', async () => {
    const { wrapper } = await mountDash(EMPTY)
    expect(wrapper.get('[data-testid="dashboard-empty"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="dashboard-featured"]').exists()).toBe(false)
    expect(wrapper.findAll('[data-testid="dashboard-project-card"]')).toHaveLength(0)
  })

  it('new-project button navigates into the wizard', async () => {
    const { wrapper, router } = await mountDash()
    await wrapper.get('[data-testid="dashboard-new-project"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('wizard')
    expect(router.currentRoute.value.params.id).toBe('new')
  })
})
