import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import SetupEvalView from '@/views/SetupEvalView.vue'
import { server } from '@/mocks/server'

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

const RUN = {
  id: 'run-48',
  project_id: 'p1',
  adapt_run_id: 'a1',
  service_job_id: 'job-1',
  status: 'succeeded',
  metrics_json: { map: 0.891, f1_macro: 0.872, epochs: 30 },
  started_at: '2026-05-30T15:12:00Z',
  ended_at: '2026-05-30T15:24:00Z',
  error_text: null,
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/projects/:id/setup-eval/:runId', name: 'setup-eval', component: SetupEvalView },
      { path: '/projects/:id/training/:runId', name: 'training', component: { template: '<div />' } },
      { path: '/projects/:id/eval/:runId', name: 'eval', component: { template: '<div />' } },
    ],
  })
}

async function mountSetup() {
  server.use(
    http.get('*/api/projects/:id/training', () => HttpResponse.json(env([RUN]))),
    http.get('*/api/training/:runId/eval', () =>
      HttpResponse.json(
        env({
          run_id: 'run-48',
          metrics: {
            map: 0.891,
            f1_macro: 0.872,
            precision_macro: 0.88,
            recall_macro: 0.86,
            per_component: [],
            false_positives: 0,
            false_negatives: 0,
          },
          predictions: [],
          prev_metrics: null,
        }),
      ),
    ),
  )
  const router = makeRouter()
  await router.push('/projects/p1/setup-eval/run-48')
  await router.isReady()
  const wrapper = mount(SetupEvalView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

describe('SetupEvalView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders HITL banner, model card, test-set picker and readiness gates', async () => {
    const { wrapper } = await mountSetup()
    expect(wrapper.find('[data-testid="setupeval-hitl"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="setupeval-model"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="setupeval-testset"]').exists()).toBe(true)
    const gates = wrapper.get('[data-testid="setupeval-readiness"]').text()
    expect(gates).toContain('0.80')
  })

  it('surfaces the real training metrics on the model card (labelled train)', async () => {
    const { wrapper } = await mountSetup()
    expect(wrapper.get('[data-testid="setupeval-model"]').text()).toContain('0.891')
  })

  it('start navigates to the eval review screen', async () => {
    const { wrapper, router } = await mountSetup()
    await wrapper.get('[data-testid="setupeval-start"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('eval')
  })
})
