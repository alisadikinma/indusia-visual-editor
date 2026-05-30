import { describe, expect, it, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import LabelingView from '@/views/LabelingView.vue'
import { server } from '@/mocks/server'

// LSFEmbed dynamically loads /lsf/main.js — stub it so the view mounts headless.
vi.mock('@/components/labeling/LSFEmbed.vue', () => ({
  default: { name: 'LSFEmbed', template: '<div data-testid="lsf-stub" />' },
}))

const env = <T,>(data: T) => ({ status: true, message: 'ok', data })

const TASK = {
  config: '<View></View>',
  task: { id: 50, data: { image: '/x.jpg' }, predictions: [{}], annotations: [] },
  side: 'top',
  designator_count: 18,
}

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div />' } },
      { path: '/projects/:id/labeling', name: 'labeling', component: LabelingView },
      { path: '/projects/:id/gate1', name: 'gate1', component: { template: '<div>g1</div>' } },
    ],
  })
}

async function mountLabeling(query = '') {
  server.use(http.get('*/api/projects/:id/labels/task', () => HttpResponse.json(env(TASK))))
  const router = makeRouter()
  await router.push(`/projects/p1/labeling${query}`)
  await router.isReady()
  const wrapper = mount(LabelingView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return { wrapper, router }
}

describe('LabelingView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders the action strip with side toggle, refresh, and the LSF canvas', async () => {
    const { wrapper } = await mountLabeling()
    expect(wrapper.find('[data-testid="labeling-strip"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="labeling-side-top"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="labeling-side-bottom"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="labeling-refresh"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="lsf-stub"]').exists()).toBe(true)
  })

  it('shows the labeled-regions count and a continue-to-training action', async () => {
    const { wrapper } = await mountLabeling()
    expect(wrapper.get('[data-testid="labeling-footer"]').text()).toContain('18')
    expect(wrapper.find('[data-testid="labeling-continue"]').exists()).toBe(true)
  })

  it('continue navigates to Gate 1', async () => {
    const { wrapper, router } = await mountLabeling()
    await wrapper.get('[data-testid="labeling-continue"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('gate1')
  })

  it('shows the correction banner with the flagged-sample counter', async () => {
    const { wrapper } = await mountLabeling('?correction=1&samples=a,b,c&run=47')
    const banner = wrapper.get('[data-testid="labeling-correction-banner"]')
    expect(banner.text()).toContain('3')
  })
})
