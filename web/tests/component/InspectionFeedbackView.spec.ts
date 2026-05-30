import { describe, expect, it, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import type { FeedbackItem } from '@/api/inspectionFeedback'

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

const rows: FeedbackItem[] = [
  makeRow({ id: 'fb-1', designator: 'R12', status: 'new', model_verdict: 'pass' }),
  makeRow({ id: 'fb-2', designator: 'C4', status: 'curated', operator_mark: 'escape' }),
]

vi.mock('@/api/inspectionFeedback', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/inspectionFeedback')>()
  return {
    ...actual,
    listFeedback: vi.fn(async () => rows.map((r) => ({ ...r }))),
    curateFeedback: vi.fn(async (id: string, body: { operator_mark?: string }) => ({
      ...rows.find((r) => r.id === id)!,
      operator_mark: body.operator_mark ?? null,
      status: 'curated' as const,
    })),
    promoteFeedback: vi.fn(async () => ({})),
  }
})

import * as feedbackApi from '@/api/inspectionFeedback'
import InspectionFeedbackView from '@/views/InspectionFeedbackView.vue'

const curateSpy = vi.mocked(feedbackApi.curateFeedback)
const promoteSpy = vi.mocked(feedbackApi.promoteFeedback)

async function mountView() {
  const wrapper = mount(InspectionFeedbackView, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('InspectionFeedbackView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    curateSpy.mockClear()
    promoteSpy.mockClear()
  })

  it('fetches on mount and renders a row per feedback item', async () => {
    const w = await mountView()
    const tableRows = w.findAll('[data-testid="feedback-row"]')
    expect(tableRows.length).toBe(2)
    expect(w.get('[data-testid="feedback-table"]').text()).toContain('R12')
  })

  it('clicking "Defect lolos" curates the row as escape', async () => {
    const w = await mountView()
    await w.get('[data-testid="feedback-escape-fb-1"]').trigger('click')
    await flushPromises()
    expect(curateSpy).toHaveBeenCalledWith('fb-1', { operator_mark: 'escape', status: 'curated' })
  })

  it('renders the explainer banner', async () => {
    const w = await mountView()
    expect(w.find('[data-testid="feedback-banner"]').exists()).toBe(true)
  })

  it('shows the promote action on a curated escape row and promotes on click', async () => {
    const w = await mountView()
    const promoteBtn = w.find('[data-testid="feedback-promote-fb-2"]')
    expect(promoteBtn.exists()).toBe(true)
    await promoteBtn.trigger('click')
    await flushPromises()
    expect(promoteSpy).toHaveBeenCalledWith('fb-2')
  })
})
