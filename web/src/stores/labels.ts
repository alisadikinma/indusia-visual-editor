import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as labelsApi from '@/api/labels'
import type { LsfTaskEnvelope, Side } from '@/api/labels'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

// A prediction below this confidence is flagged for operator review (S4).
// This is a review nudge, not a pass/fail gate — the two HITL gates stay the
// authority on what trains/ships. (ai-visual-inspection-expert §9: low score =
// uncertain → route to a human.)
export const LOW_CONFIDENCE_THRESHOLD = 0.5

export const useLabelsStore = defineStore('labels', () => {
  const projectId = ref<string | null>(null)
  const side = ref<Side>('top')
  const task = ref<LsfTaskEnvelope | null>(null)
  const selectedRegionId = ref<string | null>(null)

  const loading = ref(false)
  const refreshing = ref(false)
  const submitting = ref(false)
  const error = ref<string | null>(null)
  const lastSavedAt = ref<string | null>(null)
  const correctionMode = ref(false)
  const correctionSampleIds = ref<string[]>([])

  const designatorCount = computed(() => task.value?.designator_count ?? 0)
  const predictionCount = computed(() => {
    const preds = task.value?.task?.predictions ?? []
    return preds.length
  })

  // Per-region predictions flagged below the confidence threshold (S4).
  const lowConfidenceRegions = computed(() => {
    const preds = task.value?.task?.predictions ?? []
    return preds
      .flatMap((p) => p.result ?? [])
      .filter((r) => typeof r.score === 'number' && r.score < LOW_CONFIDENCE_THRESHOLD)
  })
  const lowConfidenceCount = computed(() => lowConfidenceRegions.value.length)
  const lowConfidenceDesignators = computed(() =>
    lowConfidenceRegions.value
      .map((r) => r.value?.rectanglelabels?.[0])
      .filter((d): d is string => typeof d === 'string' && d.length > 0),
  )

  function reset() {
    projectId.value = null
    task.value = null
    selectedRegionId.value = null
    error.value = null
    lastSavedAt.value = null
    correctionMode.value = false
    correctionSampleIds.value = []
  }

  async function loadTask(nextProjectId: string, nextSide: Side = side.value): Promise<void> {
    loading.value = true
    error.value = null
    projectId.value = nextProjectId
    side.value = nextSide
    try {
      task.value = await labelsApi.getTask(nextProjectId, nextSide)
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load labeling task')
      task.value = null
    } finally {
      loading.value = false
    }
  }

  async function refreshPredictions(): Promise<void> {
    if (!projectId.value) return
    refreshing.value = true
    error.value = null
    try {
      await labelsApi.runPrelabel(projectId.value, side.value)
      task.value = await labelsApi.getTask(projectId.value, side.value)
    } catch (err) {
      error.value = extractMessage(err, 'Failed to refresh AI predictions')
    } finally {
      refreshing.value = false
    }
  }

  async function switchSide(next: Side): Promise<void> {
    if (next === side.value || !projectId.value) return
    await loadTask(projectId.value, next)
  }

  async function submit(lsJson: unknown): Promise<void> {
    if (!projectId.value) return
    submitting.value = true
    error.value = null
    try {
      const saved = await labelsApi.submitLabels(projectId.value, side.value, lsJson)
      lastSavedAt.value = saved.snapshot_at
    } catch (err) {
      error.value = extractMessage(err, 'Failed to save labels')
      throw err
    } finally {
      submitting.value = false
    }
  }

  function setCorrectionMode(enabled: boolean, sampleIds: string[] = []) {
    correctionMode.value = enabled
    correctionSampleIds.value = sampleIds
  }

  function setSelectedRegion(id: string | null) {
    selectedRegionId.value = id
  }

  return {
    projectId,
    side,
    task,
    selectedRegionId,
    loading,
    refreshing,
    submitting,
    error,
    lastSavedAt,
    correctionMode,
    correctionSampleIds,
    designatorCount,
    predictionCount,
    lowConfidenceCount,
    lowConfidenceDesignators,
    reset,
    loadTask,
    refreshPredictions,
    switchSide,
    submit,
    setCorrectionMode,
    setSelectedRegion,
  }
})
