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

function splitPayload(unstable: boolean) {
  return env({
    model_name: 'pcb_1',
    seed: 99,
    test_pct: 15,
    min_test_per_class: 25,
    per_component: [
      {
        component: 'R1',
        train_count: 64,
        test_count: 30,
        per_class_test_counts: { good: 16, ng: 14 },
        unstable: false,
        unstable_classes: [],
      },
      {
        component: 'J5',
        train_count: 40,
        test_count: unstable ? 5 : 40,
        per_class_test_counts: { good: 3, ng: unstable ? 2 : 30 },
        unstable,
        unstable_classes: unstable
          ? [{ class: 'ng', count: 2, reason: 'hanya 2 sampel test (<25)' }]
          : [],
      },
    ],
  })
}

async function mountSetup(unstable = true) {
  server.use(
    http.get('*/api/projects/:id/training', () => HttpResponse.json(env([RUN]))),
    http.get('*/api/projects/:id/training/split-status', () =>
      HttpResponse.json(splitPayload(unstable)),
    ),
  )
  const router = makeRouter()
  await router.push('/projects/p1/setup-eval/run-48')
  await router.isReady()
  const wrapper = mount(SetupEvalView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper }
}

describe('SetupEvalView locked split indicator (S5)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the locked seed and total test count when holdout is active', async () => {
    const { wrapper } = await mountSetup(false)
    const indicator = wrapper.find('[data-testid="setupeval-locked-split"]')
    expect(indicator.exists()).toBe(true)
    expect(indicator.text()).toContain('99') // seed
    expect(indicator.text()).toContain('70') // 30 + 40 total test images
  })

  it('renders the below-floor warning listing the unstable class', async () => {
    const { wrapper } = await mountSetup(true)
    const warn = wrapper.find('[data-testid="setupeval-belowfloor"]')
    expect(warn.exists()).toBe(true)
    expect(warn.text()).toContain('J5')
    expect(warn.text().toLowerCase()).toContain('ng')
  })

  it('hides the below-floor warning when every class clears the floor', async () => {
    const { wrapper } = await mountSetup(false)
    expect(wrapper.find('[data-testid="setupeval-locked-split"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="setupeval-belowfloor"]').exists()).toBe(false)
  })
})
