import { describe, expect, it, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const sampleTask = {
  config: '<View><Image name="image" value="$image" /></View>',
  task: {
    id: 1,
    data: { image: 'http://example/image.jpg' },
    predictions: [{ id: 1, model_version: 'mock', result: [] }],
    annotations: [],
  },
  side: 'top' as const,
  designator_count: 5,
}

vi.mock('@/api/labels', () => ({
  getTask: vi.fn(async () => sampleTask),
  submitLabels: vi.fn(async (projectId: string, side: 'top' | 'bottom') => ({
    id: 'label-1',
    project_id: projectId,
    side,
    version: 1,
    snapshot_at: '2026-05-27T10:00:00Z',
  })),
  runPrelabel: vi.fn(async () => ({ id: 'pl-1' })),
  listLabels: vi.fn(async () => []),
}))

import { useLabelsStore } from '@/stores/labels'

describe('labels store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads task and exposes designator + prediction counts', async () => {
    const store = useLabelsStore()
    await store.loadTask('proj-1', 'top')
    expect(store.task?.config).toContain('<View>')
    expect(store.designatorCount).toBe(5)
    expect(store.predictionCount).toBe(1)
  })

  it('switchSide reloads task on change', async () => {
    const api = await import('@/api/labels')
    const store = useLabelsStore()
    await store.loadTask('proj-1', 'top')
    await store.switchSide('bottom')
    expect(api.getTask).toHaveBeenCalledTimes(2)
    expect(store.side).toBe('bottom')
  })

  it('submit records lastSavedAt', async () => {
    const store = useLabelsStore()
    await store.loadTask('proj-1', 'top')
    await store.submit({ result: [] })
    expect(store.lastSavedAt).toBe('2026-05-27T10:00:00Z')
  })

  it('flags predictions below the low-confidence threshold', async () => {
    const store = useLabelsStore()
    await store.loadTask('proj-1', 'top')
    store.task = {
      ...sampleTask,
      task: {
        ...sampleTask.task,
        predictions: [
          {
            model_version: 'mock',
            result: [
              { id: 'a', type: 'rectanglelabels', score: 0.92, value: { rectanglelabels: ['R1'] } },
              { id: 'b', type: 'rectanglelabels', score: 0.31, value: { rectanglelabels: ['C4'] } },
              { id: 'c', type: 'rectanglelabels', score: 0.1, value: { rectanglelabels: ['U7'] } },
            ],
          },
        ],
      },
    }
    expect(store.lowConfidenceCount).toBe(2)
    expect(store.lowConfidenceDesignators).toEqual(['C4', 'U7'])
  })

  it('correctionMode toggles with sample ids', () => {
    const store = useLabelsStore()
    store.setCorrectionMode(true, ['s1', 's2', 's3'])
    expect(store.correctionMode).toBe(true)
    expect(store.correctionSampleIds.length).toBe(3)
    store.setCorrectionMode(false)
    expect(store.correctionMode).toBe(false)
    expect(store.correctionSampleIds.length).toBe(0)
  })
})
