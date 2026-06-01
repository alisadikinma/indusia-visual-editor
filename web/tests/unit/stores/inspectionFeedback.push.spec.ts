import { describe, expect, it, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { useInspectionFeedbackStore } from '@/stores/inspectionFeedback'

const env = <T>(data: T) => ({ status: true, message: 'ok', data })

describe('inspectionFeedback push', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('pushAllPromoted sums per-project reports', async () => {
    const report = {
      model_name: 'm',
      total: 6,
      pushed: 4,
      skipped_ocr: 1,
      missing_crop: 1,
      needs_real_data: 1,
      by_track: {},
    }
    const seen: string[] = []
    server.use(
      http.post('*/api/projects/:id/defect-examples/push', ({ params }) => {
        seen.push(String(params.id))
        return HttpResponse.json(env(report))
      }),
    )

    const store = useInspectionFeedbackStore()
    await store.pushAllPromoted(['p1', 'p2'])

    expect(seen).toEqual(['p1', 'p2'])
    expect(store.pushReport).toEqual({
      total: 12,
      pushed: 8,
      skippedOcr: 2,
      missingCrop: 2,
      needsRealData: 2,
    })
    expect(store.pushing).toBe(false)
  })

  it('captures error and clears pushing on failure', async () => {
    server.use(
      http.post('*/api/projects/:id/defect-examples/push', () =>
        HttpResponse.json({ status: false, message: 'boom', data: null }, { status: 502 }),
      ),
    )
    const store = useInspectionFeedbackStore()
    await store.pushAllPromoted(['p1'])
    expect(store.error).toBeTruthy()
    expect(store.pushing).toBe(false)
  })
})
