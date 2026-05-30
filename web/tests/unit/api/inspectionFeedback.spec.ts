import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import {
  listFeedback,
  ingestFeedback,
  curateFeedback,
  promoteFeedback,
  type FeedbackItem,
  type DefectExample,
} from '@/api/inspectionFeedback'

const env = <T>(data: T) => ({ status: true, message: 'ok', data })

const row: FeedbackItem = {
  id: 'fb-1',
  project_id: 'p-1',
  edge_id: 'edge-01',
  train_run_id: 'tr-1',
  designator: 'R12',
  model_verdict: 'pass',
  operator_mark: null,
  defect_criterion: null,
  roi_path: null,
  roi_sha256: null,
  status: 'new',
  inspection_ts: '2026-05-30T01:00:00Z',
  created_at: '2026-05-30T01:00:01Z',
}

describe('inspectionFeedback api', () => {
  it('listFeedback parses rows from the envelope', async () => {
    server.use(
      http.get('*/api/inspection-feedback', ({ request }) => {
        expect(new URL(request.url).searchParams.get('status')).toBe('new')
        return HttpResponse.json(env([row]))
      }),
    )
    const rows = await listFeedback('new')
    expect(rows).toHaveLength(1)
    expect(rows[0].designator).toBe('R12')
  })

  it('listFeedback without status omits the query param', async () => {
    server.use(
      http.get('*/api/inspection-feedback', ({ request }) => {
        expect(new URL(request.url).searchParams.has('status')).toBe(false)
        return HttpResponse.json(env([row]))
      }),
    )
    const rows = await listFeedback()
    expect(rows).toHaveLength(1)
  })

  it('ingestFeedback posts multipart and returns the created row', async () => {
    server.use(
      http.post('*/api/projects/:id/inspection-feedback', async ({ request, params }) => {
        expect(params.id).toBe('p-1')
        const form = await request.formData()
        expect(form.get('designator')).toBe('R12')
        expect(form.get('model_verdict')).toBe('pass')
        return HttpResponse.json(env(row), { status: 201 })
      }),
    )
    const created = await ingestFeedback('p-1', {
      designator: 'R12',
      model_verdict: 'pass',
    })
    expect(created.id).toBe('fb-1')
  })

  it('curateFeedback puts the body and returns the updated row', async () => {
    server.use(
      http.put('*/api/inspection-feedback/:fid', async ({ request, params }) => {
        expect(params.fid).toBe('fb-1')
        const body = (await request.json()) as { operator_mark?: string }
        expect(body.operator_mark).toBe('escape')
        return HttpResponse.json(env({ ...row, operator_mark: 'escape', status: 'curated' }))
      }),
    )
    const updated = await curateFeedback('fb-1', { operator_mark: 'escape' })
    expect(updated.operator_mark).toBe('escape')
    expect(updated.status).toBe('curated')
  })

  it('promoteFeedback posts to /promote and returns the defect example', async () => {
    const example: DefectExample = {
      id: 'de-1',
      project_id: 'p-1',
      source_feedback_id: 'fb-1',
      designator: 'R12',
      defect_criterion: 'missing_component',
      roi_path: 'p-1/feedback/abc.jpg',
      roi_sha256: 'a'.repeat(64),
      created_at: '2026-05-30T02:00:00Z',
    }
    server.use(
      http.post('*/api/inspection-feedback/:fid/promote', ({ params }) => {
        expect(params.fid).toBe('fb-1')
        return HttpResponse.json(env(example), { status: 201 })
      }),
    )
    const created = await promoteFeedback('fb-1')
    expect(created.source_feedback_id).toBe('fb-1')
  })
})
