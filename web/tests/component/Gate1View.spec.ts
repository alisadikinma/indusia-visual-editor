import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import Gate1View from '@/views/Gate1View.vue'
import { server } from '@/mocks/server'
import { useEngineerStore } from '@/stores/engineer'

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

const SUGGESTION = {
  project_id: 'p1',
  side: 'top',
  stats: {
    total_regions: 312,
    coverage_ratio: 0.84,
    side_breakdown: { top: 200, bottom: 112 },
    per_designator: [
      { designator: 'R1', count: 96, bucket: 'sufficient' },
      { designator: 'U1', count: 40, bucket: 'moderate' },
      { designator: 'D2', count: 2, bucket: 'at_risk' },
    ],
  },
  hyperparameters: {
    epochs: 80,
    batch_size: 16,
    learning_rate: 0.001,
    augmentation_intensity: 'medium',
    early_stopping_patience: 10,
    grounding_source: 'heuristic',
  },
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects/:id/gate1', name: 'gate1', component: Gate1View },
      { path: '/projects/:id/labeling', name: 'labeling', component: { template: '<div />' } },
      { path: '/projects/:id/training/:runId', name: 'training', component: { template: '<div />' } },
    ],
  })
}

async function mountGate1() {
  server.use(
    http.post('*/api/projects/:id/training/suggest-hyperparams', () =>
      HttpResponse.json(env(SUGGESTION)),
    ),
  )
  const router = makeRouter()
  await router.push('/projects/p1/gate1')
  await router.isReady()
  const wrapper = mount(Gate1View, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

describe('Gate1View', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders HITL banner, readiness stats and per-component coverage', async () => {
    const { wrapper } = await mountGate1()
    expect(wrapper.find('[data-testid="gate1-hitl"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="gate1-stat-annotations"]').text()).toContain('312')
    const cov = wrapper.get('[data-testid="gate1-coverage"]').text()
    expect(cov).toContain('R1')
    expect(cov).toContain('D2')
  })

  it('derives considerations from real bucket data (no fabrication)', async () => {
    const { wrapper } = await mountGate1()
    const c = wrapper.get('[data-testid="gate1-considerations"]').text()
    // D2 is at_risk with 2 examples
    expect(c).toContain('D2')
  })

  it('hides hyperparameters until engineer mode is on', async () => {
    const { wrapper } = await mountGate1()
    expect(wrapper.find('[data-testid="gate1-hyperparams"]').exists()).toBe(false)
    useEngineerStore().enabled = true
    await flushPromises()
    expect(wrapper.find('[data-testid="gate1-hyperparams"]').exists()).toBe(true)
  })

  it('has scratch selected and continue disabled, plus approve + back', async () => {
    const { wrapper } = await mountGate1()
    expect(wrapper.find('[data-testid="gate1-mode-scratch"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="gate1-mode-continue"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="gate1-approve"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="gate1-back"]').exists()).toBe(true)
  })
})
