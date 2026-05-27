import { describe, expect, it, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

function metrics(map: number, f1: number, perCompF1: number[]) {
  return {
    map,
    f1_macro: f1,
    precision_macro: f1,
    recall_macro: f1,
    per_component: perCompF1.map((f, i) => ({
      designator: `D${i + 1}`,
      f1: f,
      precision: f,
      recall: f,
      support: 10,
      pass: f >= 0.7,
    })),
    false_positives: 1,
    false_negatives: 2,
  }
}

vi.mock('@/api/eval', async () => {
  const actual =
    (await vi.importActual<typeof import('@/api/eval')>('@/api/eval')) as typeof import('@/api/eval')
  return {
    ...actual,
    getEval: vi.fn(async (runId: string) => ({
      run_id: runId,
      metrics: metrics(0.85, 0.84, [0.75, 0.82, 0.71]),
      predictions: [],
      prev_metrics: null,
    })),
  }
})

import { useEvalStore } from '@/stores/eval'

describe('eval store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('classifies passed when all thresholds met', async () => {
    const store = useEvalStore()
    await store.load('run-1')
    expect(store.verdict).toBe('passed')
    expect(store.canPromote).toBe(true)
    expect(store.failingComponents.length).toBe(0)
  })

  it('classifies failing when per-component F1 below 0.7', async () => {
    const api = await import('@/api/eval')
    vi.mocked(api.getEval).mockResolvedValueOnce({
      run_id: 'run-2',
      metrics: metrics(0.85, 0.82, [0.75, 0.65, 0.71]),
      predictions: [],
      prev_metrics: null,
    })
    const store = useEvalStore()
    await store.load('run-2')
    expect(store.verdict).toBe('failing')
    expect(store.canPromote).toBe(false)
    expect(store.failingComponents.length).toBe(1)
    expect(store.failingComponents[0].designator).toBe('D2')
  })

  it('classifies corrected when verdict still below but hasCorrections is true', async () => {
    const api = await import('@/api/eval')
    vi.mocked(api.getEval).mockResolvedValueOnce({
      run_id: 'run-3',
      metrics: metrics(0.85, 0.82, [0.75, 0.65, 0.71]),
      predictions: [],
      prev_metrics: null,
    })
    const store = useEvalStore()
    await store.load('run-3')
    store.setHasCorrections(true)
    expect(store.verdict).toBe('corrected')
  })

  it('classifies failing when mAP below 0.80', async () => {
    const api = await import('@/api/eval')
    vi.mocked(api.getEval).mockResolvedValueOnce({
      run_id: 'run-4',
      metrics: metrics(0.78, 0.85, [0.75, 0.82, 0.71]),
      predictions: [],
      prev_metrics: null,
    })
    const store = useEvalStore()
    await store.load('run-4')
    expect(store.verdict).toBe('failing')
  })

  it('wrongCount sums fp + fn', async () => {
    const store = useEvalStore()
    await store.load('run-1')
    expect(store.wrongCount).toBe(3)
  })
})
