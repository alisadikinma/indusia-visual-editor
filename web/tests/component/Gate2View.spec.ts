import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import Gate2View from '@/views/Gate2View.vue'
import { server } from '@/mocks/server'
import { useEngineerStore } from '@/stores/engineer'

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

function evalData(pass: boolean) {
  return {
    run_id: 'run-48',
    metrics: {
      map: 0.891,
      f1_macro: 0.87,
      precision_macro: 0.923,
      recall_macro: 0.89,
      false_positives: 2,
      false_negatives: 3,
      per_component: [{ designator: 'J5', f1: pass ? 0.78 : 0.63, precision: 0.8, recall: 0.76, support: 14, pass }],
    },
    predictions: [],
    prev_metrics: null,
  }
}

const EDGES = [
  { id: 'e1', name: 'EDGE-01 · Line A', webhook_url: 'https://e1/h', version_policy: { mode: 'auto_pull_latest' }, registered_at: '', last_seen_at: new Date(Date.now() - 30_000).toISOString() },
  { id: 'e4', name: 'EDGE-04 · Line B', webhook_url: 'https://e4/h', version_policy: { mode: 'auto_pull_latest' }, registered_at: '', last_seen_at: null },
]

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div />' } },
      { path: '/projects/:id/eval/:runId/gate2', name: 'gate2', component: Gate2View },
      { path: '/projects/:id/eval/:runId', name: 'eval', component: { template: '<div />' } },
    ],
  })
}

async function mountGate2(pass = true) {
  server.use(
    http.get('*/api/training/:runId/eval', () => HttpResponse.json(env(evalData(pass)))),
    http.get('*/api/edges', () => HttpResponse.json(env(EDGES))),
    http.post('*/api/projects/:id/deploy', () =>
      HttpResponse.json(env({ id: 'd1', project_id: 'p1', train_run_id: 'run-48', model_version: 'v20260530-001', edges_notified: [], deployed_at: '2026-05-30T00:00:00Z' })),
    ),
  )
  const router = makeRouter()
  await router.push('/projects/p1/eval/run-48/gate2')
  await router.isReady()
  const wrapper = mount(Gate2View, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

describe('Gate2View', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('passed eval: green banner, edges listed, deploy gated on confirm checkbox', async () => {
    const { wrapper } = await mountGate2(true)
    expect(wrapper.get('[data-testid="gate2-banner"]').attributes('data-state')).toBe('passed')
    expect(wrapper.get('[data-testid="gate2-edges"]').text()).toContain('EDGE-01')
    const deploy = wrapper.get('[data-testid="gate2-deploy"]')
    expect(deploy.attributes('disabled')).toBeDefined()
    await wrapper.get('[data-testid="gate2-confirm"]').setValue(true)
    await flushPromises()
    expect(wrapper.get('[data-testid="gate2-deploy"]').attributes('disabled')).toBeUndefined()
  })

  it('blocked eval: red banner and deploy stays disabled even when confirmed', async () => {
    const { wrapper } = await mountGate2(false)
    expect(wrapper.get('[data-testid="gate2-banner"]').attributes('data-state')).toBe('blocked')
    await wrapper.get('[data-testid="gate2-confirm"]').setValue(true)
    await flushPromises()
    expect(wrapper.get('[data-testid="gate2-deploy"]').attributes('disabled')).toBeDefined()
  })

  it('surfaces the offline-edge warning', async () => {
    const { wrapper } = await mountGate2(true)
    expect(wrapper.text()).toContain('EDGE-04')
  })

  it('hides technical deploy details until engineer mode is on', async () => {
    const { wrapper } = await mountGate2(true)
    expect(wrapper.find('[data-testid="gate2-tech"]').exists()).toBe(false)
    useEngineerStore().enabled = true
    await flushPromises()
    expect(wrapper.find('[data-testid="gate2-tech"]').exists()).toBe(true)
  })

  it('promote flows through the confirm modal and navigates to dashboard', async () => {
    const { wrapper, router } = await mountGate2(true)
    await wrapper.get('[data-testid="gate2-confirm"]').setValue(true)
    await flushPromises()
    await wrapper.get('[data-testid="gate2-deploy"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="gate2-modal-confirm"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('dashboard')
  })
})
