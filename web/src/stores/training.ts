import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as trainingApi from '@/api/training'
import type {
  DatasetStats,
  HyperparamsSuggestion,
  TrainRun,
  TrainStatus,
} from '@/api/training'
import type { Side } from '@/api/labels'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

interface LiveMetrics {
  epoch: number
  total_epochs: number
  loss: number | null
  map: number | null
  f1: number | null
  precision: number | null
  recall: number | null
  eta_seconds: number | null
  gpu_mem_used_gb: number | null
  gpu_mem_total_gb: number | null
  log_line: string | null
}

interface PerCompState {
  designator: string
  state: 'queued' | 'training' | 'done'
}

export const useTrainingStore = defineStore('training', () => {
  const datasetStats = ref<DatasetStats | null>(null)
  const hyperparams = ref<HyperparamsSuggestion | null>(null)
  const currentRun = ref<TrainRun | null>(null)
  const live = ref<LiveMetrics>({
    epoch: 0,
    total_epochs: 30,
    loss: null,
    map: null,
    f1: null,
    precision: null,
    recall: null,
    eta_seconds: null,
    gpu_mem_used_gb: null,
    gpu_mem_total_gb: null,
    log_line: null,
  })
  const perComponent = ref<PerCompState[]>([])
  const logLines = ref<string[]>([])
  const trainMode = ref<'scratch' | 'continue'>('scratch')

  const loading = ref(false)
  const starting = ref(false)
  const streaming = ref(false)
  const error = ref<string | null>(null)

  let eventSource: EventSource | null = null

  const status = computed<TrainStatus>(() => currentRun.value?.status ?? 'pending')
  const isTerminal = computed(
    () =>
      currentRun.value != null &&
      ['succeeded', 'failed', 'cancelled'].includes(currentRun.value.status),
  )
  const progressPct = computed(() => {
    if (!live.value.total_epochs) return 0
    return Math.min(100, Math.round((live.value.epoch / live.value.total_epochs) * 100))
  })

  function reset() {
    closeStream()
    datasetStats.value = null
    hyperparams.value = null
    currentRun.value = null
    perComponent.value = []
    logLines.value = []
    error.value = null
    live.value = {
      epoch: 0,
      total_epochs: 30,
      loss: null,
      map: null,
      f1: null,
      precision: null,
      recall: null,
      eta_seconds: null,
      gpu_mem_used_gb: null,
      gpu_mem_total_gb: null,
      log_line: null,
    }
  }

  async function loadGate1(projectId: string, side: Side = 'top'): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const suggestion = await trainingApi.suggestHyperparams(projectId, side)
      hyperparams.value = suggestion
      datasetStats.value = suggestion.stats
      live.value.total_epochs = suggestion.hyperparameters.epochs
      perComponent.value = suggestion.stats.per_designator.map((p) => ({
        designator: p.designator,
        state: 'queued',
      }))
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load Gate 1 readiness')
    } finally {
      loading.value = false
    }
  }

  async function start(projectId: string): Promise<TrainRun | null> {
    starting.value = true
    error.value = null
    try {
      const run = await trainingApi.startTraining(projectId)
      currentRun.value = run
      return run
    } catch (err) {
      error.value = extractMessage(err, 'Failed to start training')
      return null
    } finally {
      starting.value = false
    }
  }

  async function loadRun(projectId: string, runId: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const runs = await trainingApi.listTrainRuns(projectId)
      currentRun.value = runs.find((r) => r.id === runId) ?? null
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load training run')
    } finally {
      loading.value = false
    }
  }

  function openStream(runId: string): void {
    closeStream()
    streaming.value = true
    eventSource = new EventSource(trainingApi.streamTrainingUrl(runId))
    eventSource.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data) as Record<string, unknown>
        applyEvent(payload)
      } catch {
        /* ignore malformed */
      }
    }
    eventSource.onerror = () => {
      streaming.value = false
      eventSource?.close()
      eventSource = null
    }
  }

  function applyEvent(ev: Record<string, unknown>) {
    const kind = ev.event as string | undefined
    if (kind === 'running' && currentRun.value) {
      currentRun.value = { ...currentRun.value, status: 'running' }
    }
    if (kind === 'epoch') {
      const epoch = Number(ev.epoch ?? 0)
      live.value = {
        ...live.value,
        epoch,
        total_epochs: Number(ev.total_epochs ?? live.value.total_epochs),
        loss: numOrNull(ev.loss),
        map: numOrNull(ev.map),
        f1: numOrNull(ev.f1),
        precision: numOrNull(ev.precision),
        recall: numOrNull(ev.recall),
        eta_seconds: numOrNull(ev.eta_seconds),
        gpu_mem_used_gb: numOrNull(ev.gpu_mem_used_gb),
        gpu_mem_total_gb: numOrNull(ev.gpu_mem_total_gb),
        log_line: (ev.log_line as string) ?? null,
      }
      if (ev.log_line) logLines.value = [...logLines.value.slice(-49), String(ev.log_line)]
      if (Array.isArray(ev.per_component)) {
        perComponent.value = (ev.per_component as PerCompState[]).slice()
      }
    }
    if (kind === 'succeeded' && currentRun.value) {
      currentRun.value = {
        ...currentRun.value,
        status: 'succeeded',
        metrics_json: (ev.metrics as Record<string, unknown>) ?? null,
        ended_at: new Date().toISOString(),
      }
      streaming.value = false
      eventSource?.close()
    }
    if (kind === 'failed' && currentRun.value) {
      currentRun.value = {
        ...currentRun.value,
        status: 'failed',
        error_text: (ev.error as string) ?? null,
        ended_at: new Date().toISOString(),
      }
      streaming.value = false
      eventSource?.close()
    }
    if (kind === 'cancelled' && currentRun.value) {
      currentRun.value = { ...currentRun.value, status: 'cancelled' }
      streaming.value = false
      eventSource?.close()
    }
  }

  function closeStream() {
    eventSource?.close()
    eventSource = null
    streaming.value = false
  }

  return {
    datasetStats,
    hyperparams,
    currentRun,
    live,
    perComponent,
    logLines,
    trainMode,
    loading,
    starting,
    streaming,
    error,
    status,
    isTerminal,
    progressPct,
    reset,
    loadGate1,
    start,
    loadRun,
    openStream,
    closeStream,
  }
})

function numOrNull(v: unknown): number | null {
  if (v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
