import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import EvalView from '@/views/EvalView.vue'
import { server } from '@/mocks/server'
import { useEvalStore } from '@/stores/eval'

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

function evalResp(opts: { failing?: boolean }) {
  const j5f1 = opts.failing ? 0.63 : 0.91
  return {
    run_id: 'run-48',
    metrics: {
      map: 0.842,
      f1_macro: 0.86,
      precision_macro: 0.871,
      recall_macro: 0.819,
      false_positives: 5,
      false_negatives: 9,
      per_component: [
        { designator: 'R1', f1: 0.94, precision: 0.95, recall: 0.93, support: 40, pass: true },
        { designator: 'J5', f1: j5f1, precision: 0.7, recall: 0.6, support: 14, pass: !opts.failing },
      ],
    },
    predictions: [
      { id: 't1', designator: 'J5', status: 'fp', confidence: 0.62, thumbnail_url: null },
      { id: 't2', designator: 'J5', status: 'fn', confidence: 0.71, thumbnail_url: null },
      { id: 't3', designator: 'R1', status: 'tp', confidence: 0.94, thumbnail_url: null },
    ],
    prev_metrics: null,
  }
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects/:id/eval/:runId', name: 'eval', component: EvalView },
      { path: '/projects/:id/eval/:runId/gate2', name: 'gate2', component: { template: '<div />' } },
      { path: '/projects/:id/labeling', name: 'labeling', component: { template: '<div />' } },
      { path: '/projects/:id/gate1', name: 'gate1', component: { template: '<div />' } },
      { path: '/projects/:id/setup-eval/:runId', name: 'setup-eval', component: { template: '<div />' } },
    ],
  })
}

async function mountEval(failing = true) {
  server.use(
    http.get('*/api/training/:runId/eval', () => HttpResponse.json(env(evalResp({ failing })))),
  )
  const router = makeRouter()
  await router.push('/projects/p1/eval/run-48')
  await router.isReady()
  const wrapper = mount(EvalView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

describe('EvalView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('failing verdict: banner, failing components, correct-samples action', async () => {
    const { wrapper } = await mountEval(true)
    expect(wrapper.get('[data-testid="eval-banner"]').attributes('data-verdict')).toBe('failing')
    expect(wrapper.get('[data-testid="eval-failing"]').text()).toContain('J5')
    expect(wrapper.get('[data-testid="eval-action"]').text().toLowerCase()).toContain('correct')
  })

  it('passed verdict: promote action', async () => {
    const { wrapper } = await mountEval(false)
    expect(wrapper.get('[data-testid="eval-banner"]').attributes('data-verdict')).toBe('passed')
    expect(wrapper.get('[data-testid="eval-action"]').text().toLowerCase()).toContain('promote')
  })

  it('corrected verdict routes to retrain', async () => {
    const { wrapper } = await mountEval(true)
    useEvalStore().setHasCorrections(true)
    await flushPromises()
    expect(wrapper.get('[data-testid="eval-banner"]').attributes('data-verdict')).toBe('corrected')
    expect(wrapper.get('[data-testid="eval-action"]').text().toLowerCase()).toContain('retrain')
  })

  it('renders metric tiles, prediction filter chips and cards', async () => {
    const { wrapper } = await mountEval(true)
    expect(wrapper.get('[data-testid="eval-metrics"]').text()).toContain('0.842')
    expect(wrapper.find('[data-testid="eval-filters"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="eval-pred-card"]').length).toBe(3)
    // filter to FP only → 1 card
    await wrapper.get('[data-testid="eval-filter-fp"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="eval-pred-card"]').length).toBe(1)
  })

  it('promote navigates to Gate 2', async () => {
    const { wrapper, router } = await mountEval(false)
    await wrapper.get('[data-testid="eval-action"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('gate2')
  })
})
