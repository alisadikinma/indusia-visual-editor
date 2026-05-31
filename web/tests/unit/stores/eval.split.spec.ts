import { describe, expect, it, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { SplitStatus } from '@/api/split'

const split: SplitStatus = {
  modelName: 'pcb_1',
  seed: 7,
  testPct: 15,
  minTestPerClass: 25,
  perComponent: [
    {
      component: 'R1',
      trainCount: 8,
      testCount: 30,
      perClassTestCounts: { good: 3, ng: 27 },
      unstable: false,
      unstableClasses: [],
    },
    {
      component: 'J5',
      trainCount: 9,
      testCount: 2,
      perClassTestCounts: { good: 1, ng: 1 },
      unstable: true,
      unstableClasses: [{ class: 'ng', count: 1, reason: 'hanya 1 sampel test (<25)' }],
    },
  ],
}

vi.mock('@/api/split', () => ({
  getSplitStatus: vi.fn(async () => split),
}))

import { useEvalStore } from '@/stores/eval'
import * as splitApi from '@/api/split'

describe('eval store split-status', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchSplitStatus populates splitStatus + lockedSeed + belowFloor', async () => {
    const store = useEvalStore()
    expect(store.splitStatus).toBeNull()

    await store.fetchSplitStatus('p-1')

    expect(splitApi.getSplitStatus).toHaveBeenCalledWith('p-1')
    expect(store.splitStatus?.seed).toBe(7)
    expect(store.lockedSeed).toBe(7)
    expect(store.belowFloor).toBe(true)
    expect(store.unstableComponents.map((c) => c.component)).toContain('J5')
  })

  it('belowFloor false when no component is unstable', async () => {
    ;(splitApi.getSplitStatus as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ...split,
      perComponent: split.perComponent.map((c) => ({ ...c, unstable: false })),
    })
    const store = useEvalStore()
    await store.fetchSplitStatus('p-1')
    expect(store.belowFloor).toBe(false)
  })

  it('null split (no pipeline) leaves belowFloor false and seed null', async () => {
    ;(splitApi.getSplitStatus as ReturnType<typeof vi.fn>).mockResolvedValueOnce(null)
    const store = useEvalStore()
    await store.fetchSplitStatus('p-1')
    expect(store.splitStatus).toBeNull()
    expect(store.belowFloor).toBe(false)
    expect(store.lockedSeed).toBeNull()
  })

  it('error path sets error and clears split', async () => {
    ;(splitApi.getSplitStatus as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('boom'),
    )
    const store = useEvalStore()
    await store.fetchSplitStatus('p-1')
    expect(store.error).toBeTruthy()
    expect(store.splitStatus).toBeNull()
  })
})
