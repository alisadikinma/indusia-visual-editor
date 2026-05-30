import { describe, expect, it, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { FeedbackItem, DefectExample } from '@/api/inspectionFeedback'

function makeRow(over: Partial<FeedbackItem>): FeedbackItem {
  return {
    id: 'fb',
    project_id: 'p-1',
    edge_id: 'edge-01',
    train_run_id: 'tr-1',
    designator: 'R1',
    model_verdict: 'pass',
    operator_mark: null,
    defect_criterion: null,
    roi_path: null,
    roi_sha256: null,
    status: 'new',
    inspection_ts: '2026-05-30T00:00:00Z',
    created_at: '2026-05-30T00:00:01Z',
    ...over,
  }
}

const listRows: FeedbackItem[] = [
  makeRow({ id: 'fb-1', status: 'new', operator_mark: null }),
  makeRow({ id: 'fb-2', status: 'curated', operator_mark: 'escape', model_verdict: 'pass' }),
  makeRow({ id: 'fb-3', status: 'curated', operator_mark: 'overkill', model_verdict: 'fail' }),
  makeRow({ id: 'fb-4', status: 'new', operator_mark: null }),
]

vi.mock('@/api/inspectionFeedback', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/inspectionFeedback')>()
  return {
    ...actual,
    listFeedback: vi.fn(async () => listRows.map((r) => ({ ...r }))),
    curateFeedback: vi.fn(async (id: string, body: { operator_mark?: string; status?: string }) => ({
      ...listRows.find((r) => r.id === id)!,
      operator_mark: body.operator_mark ?? null,
      status: (body.status ?? 'curated') as FeedbackItem['status'],
    })),
    promoteFeedback: vi.fn(
      async (id: string): Promise<DefectExample> => ({
        id: 'de-1',
        project_id: 'p-1',
        source_feedback_id: id,
        designator: 'R1',
        defect_criterion: 'missing_component',
        roi_path: null,
        roi_sha256: null,
        created_at: '2026-05-30T03:00:00Z',
      }),
    ),
  }
})

import { useInspectionFeedbackStore } from '@/stores/inspectionFeedback'

describe('inspectionFeedback store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('fetchAll populates items and count getters', async () => {
    const store = useInspectionFeedbackStore()
    await store.fetchAll()
    expect(store.items).toHaveLength(4)
    expect(store.newCount).toBe(2)
    expect(store.escapeCount).toBe(1)
    expect(store.overkillCount).toBe(1)
  })

  it('curate flips the row mark and status optimistically', async () => {
    const store = useInspectionFeedbackStore()
    await store.fetchAll()
    await store.curate('fb-1', { operator_mark: 'escape' })
    const row = store.items.find((r) => r.id === 'fb-1')!
    expect(row.operator_mark).toBe('escape')
    expect(store.escapeCount).toBe(2)
  })

  it('promote flips that row to promoted status', async () => {
    const store = useInspectionFeedbackStore()
    await store.fetchAll()
    await store.promote('fb-2')
    const row = store.items.find((r) => r.id === 'fb-2')!
    expect(row.status).toBe('promoted')
  })
})
