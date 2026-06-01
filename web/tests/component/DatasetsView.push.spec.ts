import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import DatasetsView from '@/views/DatasetsView.vue'
import { server } from '@/mocks/server'

const env = <T>(data: T) => ({ status: true, message: 'ok', data })

function seedHandlers() {
  server.use(
    http.get('*/api/datasets', () => HttpResponse.json(env([]))),
    http.get('*/api/defect-examples/summary', () =>
      HttpResponse.json(
        env({
          floor: 100,
          classes: [
            { defect_criterion: 'missing_component', count: 12, meets_floor: false },
          ],
        }),
      ),
    ),
    http.get('*/api/projects', () =>
      HttpResponse.json(env([{ id: 'p1', name: 'A', slug: 'a', status: 'drafting' }])),
    ),
    http.post('*/api/projects/:id/defect-examples/push', () =>
      HttpResponse.json(
        env({
          model_name: 'pcb_1',
          total: 6,
          pushed: 4,
          skipped_ocr: 1,
          missing_crop: 0,
          needs_real_data: 1,
          by_track: {},
        }),
      ),
    ),
  )
}

describe('DatasetsView push to trainer (T1 S8)', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('renders the push button and shows the report after a push', async () => {
    seedHandlers()
    const w = mount(DatasetsView, { attachTo: document.body })
    await flushPromises()

    const btn = w.find('[data-testid="defect-push"]')
    expect(btn.exists()).toBe(true)
    expect(w.find('[data-testid="defect-push-report"]').exists()).toBe(false)

    await btn.trigger('click')
    await flushPromises()

    const report = w.find('[data-testid="defect-push-report"]')
    expect(report.exists()).toBe(true)
    expect(report.text()).toContain('4') // pushed
    expect(report.text()).toContain('1') // skipped / needs-real
  })
})
