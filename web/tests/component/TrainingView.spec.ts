import { describe, expect, it, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import TrainingView from '@/views/TrainingView.vue'
import { server } from '@/mocks/server'
import { useTrainingStore } from '@/stores/training'
import { useEngineerStore } from '@/stores/engineer'

// EventSource is not implemented in happy-dom — stub it.
class FakeES {
  onmessage: ((e: MessageEvent) => void) | null = null
  onerror: (() => void) | null = null
  close() {}
  constructor(public url: string) {}
}
vi.stubGlobal('EventSource', FakeES)

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

const RUN = {
  id: 'run-48',
  project_id: 'p1',
  adapt_run_id: 'a1',
  service_job_id: 'job-1',
  status: 'running',
  metrics_json: null,
  started_at: '2026-05-30T15:12:00Z',
  ended_at: null,
  error_text: null,
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div />' } },
      { path: '/projects/:id/training/:runId', name: 'training', component: TrainingView },
      { path: '/projects/:id/setup-eval/:runId', name: 'setup-eval', component: { template: '<div />' } },
    ],
  })
}

async function mountTraining() {
  server.use(http.get('*/api/projects/:id/training', () => HttpResponse.json(env([RUN]))))
  const router = makeRouter()
  await router.push('/projects/p1/training/run-48')
  await router.isReady()
  const wrapper = mount(TrainingView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper }
}

describe('TrainingView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders status pill, progress strip, per-component table and live metrics', async () => {
    const { wrapper } = await mountTraining()
    const store = useTrainingStore()
    store.live = { ...store.live, epoch: 8, total_epochs: 30, map: 0.847, f1: 0.812, precision: 0.881, recall: 0.823 }
    store.perComponent = [
      { designator: 'R1', state: 'done' },
      { designator: 'J5', state: 'training' },
    ]
    await flushPromises()
    expect(wrapper.find('[data-testid="training-status"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="training-progress"]').text()).toContain('8')
    expect(wrapper.get('[data-testid="training-percomp"]').text()).toContain('R1')
    expect(wrapper.get('[data-testid="training-metrics"]').text()).toContain('0.847')
  })

  it('hides training internals until engineer mode is on', async () => {
    const { wrapper } = await mountTraining()
    expect(wrapper.find('[data-testid="training-internals"]').exists()).toBe(false)
    useEngineerStore().enabled = true
    await flushPromises()
    expect(wrapper.find('[data-testid="training-internals"]').exists()).toBe(true)
  })

  it('View results is disabled until the run succeeds', async () => {
    const { wrapper } = await mountTraining()
    const store = useTrainingStore()
    const btn = wrapper.get('[data-testid="training-results"]')
    expect(btn.attributes('disabled')).toBeDefined()
    store.currentRun = { ...RUN, status: 'succeeded' }
    await flushPromises()
    expect(wrapper.get('[data-testid="training-results"]').attributes('disabled')).toBeUndefined()
  })
})
