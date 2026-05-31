import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { getSplitStatus } from '@/api/split'

const env = <T>(data: T) => ({ status: true, message: 'ok', data })

const rawSplit = {
  model_name: 'pcb_1',
  seed: 7,
  test_pct: 15,
  min_test_per_class: 25,
  per_component: [
    {
      component: 'R1',
      train_count: 8,
      test_count: 30,
      per_class_test_counts: { good: 3, ng: 27 },
      unstable: false,
      unstable_classes: [],
    },
    {
      component: 'J5',
      train_count: 9,
      test_count: 2,
      per_class_test_counts: { good: 1, ng: 1 },
      unstable: true,
      unstable_classes: [{ class: 'ng', count: 1, reason: 'hanya 1 sampel test (<25)' }],
    },
  ],
}

describe('split api', () => {
  it('getSplitStatus normalizes the envelope to camelCase', async () => {
    server.use(
      http.get('*/api/projects/:id/training/split-status', ({ params }) => {
        expect(params.id).toBe('p-1')
        return HttpResponse.json(env(rawSplit))
      }),
    )
    const split = await getSplitStatus('p-1')
    expect(split).not.toBeNull()
    expect(split!.seed).toBe(7)
    expect(split!.testPct).toBe(15)
    expect(split!.perComponent).toHaveLength(2)
    expect(split!.perComponent[0].component).toBe('R1')
    expect(split!.perComponent[0].trainCount).toBe(8)
    expect(split!.perComponent[1].unstable).toBe(true)
    expect(split!.perComponent[1].unstableClasses[0].class).toBe('ng')
  })

  it('getSplitStatus returns null when the project has no pipeline', async () => {
    server.use(
      http.get('*/api/projects/:id/training/split-status', () =>
        HttpResponse.json(env(null)),
      ),
    )
    const split = await getSplitStatus('p-2')
    expect(split).toBeNull()
  })
})
