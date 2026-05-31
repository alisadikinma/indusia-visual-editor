import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as evalApi from '@/api/eval'
import { EVAL_THRESHOLDS, classifyEval } from '@/api/eval'
import type { EvalResponse, EvalVerdict, EvalPrediction } from '@/api/eval'
import { getSplitStatus } from '@/api/split'
import type { SplitStatus, ComponentSplit } from '@/api/split'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

export const useEvalStore = defineStore('eval', () => {
  const runId = ref<string | null>(null)
  const data = ref<EvalResponse | null>(null)
  const hasCorrections = ref(false)
  const testSet = ref<'holdout' | 'production_run' | 'upload'>('holdout')
  const predictionFilter = ref<'all' | 'fp' | 'fn' | 'tp'>('all')
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Stable held-out split status (G5 / S5 "Locked test set" indicator).
  const splitStatus = ref<SplitStatus | null>(null)

  const verdict = computed<EvalVerdict>(() => {
    if (!data.value) return 'failing'
    return classifyEval(data.value.metrics, hasCorrections.value)
  })

  const failingComponents = computed(() => {
    if (!data.value) return []
    return data.value.metrics.per_component.filter(
      (c) => c.f1 < EVAL_THRESHOLDS.per_component_f1_min,
    )
  })

  const filteredPredictions = computed<EvalPrediction[]>(() => {
    if (!data.value) return []
    if (predictionFilter.value === 'all') return data.value.predictions
    return data.value.predictions.filter((p) => p.status === predictionFilter.value)
  })

  const wrongCount = computed(() => {
    if (!data.value) return 0
    return data.value.metrics.false_positives + data.value.metrics.false_negatives
  })

  const canPromote = computed(() => verdict.value === 'passed')

  const lockedSeed = computed<number | null>(() => splitStatus.value?.seed ?? null)

  const unstableComponents = computed<ComponentSplit[]>(() =>
    (splitStatus.value?.perComponent ?? []).filter((c) => c.unstable),
  )

  // True when any component's test set is below the per-class floor — the
  // signal that drives the amber "data test kurang" warning on Setup eval.
  const belowFloor = computed<boolean>(() => unstableComponents.value.length > 0)

  async function load(id: string): Promise<void> {
    runId.value = id
    loading.value = true
    error.value = null
    try {
      data.value = await evalApi.getEval(id)
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load eval results')
      data.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchSplitStatus(projectId: string): Promise<void> {
    error.value = null
    try {
      splitStatus.value = await getSplitStatus(projectId)
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load split status')
      splitStatus.value = null
    }
  }

  function setHasCorrections(next: boolean) {
    hasCorrections.value = next
  }

  function setTestSet(next: typeof testSet.value) {
    testSet.value = next
  }

  function setFilter(next: typeof predictionFilter.value) {
    predictionFilter.value = next
  }

  function reset() {
    runId.value = null
    data.value = null
    hasCorrections.value = false
    testSet.value = 'holdout'
    predictionFilter.value = 'all'
    error.value = null
    splitStatus.value = null
  }

  return {
    runId,
    data,
    hasCorrections,
    testSet,
    predictionFilter,
    loading,
    error,
    splitStatus,
    verdict,
    failingComponents,
    filteredPredictions,
    wrongCount,
    canPromote,
    lockedSeed,
    unstableComponents,
    belowFloor,
    load,
    fetchSplitStatus,
    setHasCorrections,
    setTestSet,
    setFilter,
    reset,
  }
})
