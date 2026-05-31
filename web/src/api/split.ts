import { apiClient } from './client'

// Stable held-out split status (G5). The editor backend resolves the
// auto-inspect-service model name from the project's latest adapt run and
// proxies the read — the FE never talks to the service directly.

export interface ComponentSplit {
  component: string
  trainCount: number
  testCount: number
  perClassTestCounts: Record<string, number>
  unstable: boolean
  unstableClasses: { class: string; count: number; reason: string }[]
}

export interface SplitStatus {
  modelName: string | null
  seed: number | null
  testPct: number | null
  minTestPerClass: number | null
  perComponent: ComponentSplit[]
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

interface RawComponentSplit {
  component: string
  train_count: number
  test_count: number
  per_class_test_counts: Record<string, number>
  unstable: boolean
  unstable_classes: { class: string; count: number; reason: string }[]
}

interface RawSplitStatus {
  model_name: string | null
  seed: number | null
  test_pct: number | null
  min_test_per_class: number | null
  per_component: RawComponentSplit[]
}

function normalize(raw: RawSplitStatus): SplitStatus {
  return {
    modelName: raw.model_name ?? null,
    seed: raw.seed ?? null,
    testPct: raw.test_pct ?? null,
    minTestPerClass: raw.min_test_per_class ?? null,
    perComponent: (raw.per_component ?? []).map((c) => ({
      component: c.component,
      trainCount: c.train_count,
      testCount: c.test_count,
      perClassTestCounts: c.per_class_test_counts ?? {},
      unstable: c.unstable,
      unstableClasses: c.unstable_classes ?? [],
    })),
  }
}

/**
 * Fetch the locked split status for a project. Returns `null` when the project
 * has no prepared pipeline yet (backend sends `data: null`).
 */
export async function getSplitStatus(projectId: string): Promise<SplitStatus | null> {
  const { data } = await apiClient.get<Envelope<RawSplitStatus | null>>(
    `/projects/${projectId}/training/split-status`,
  )
  return data.data ? normalize(data.data) : null
}
