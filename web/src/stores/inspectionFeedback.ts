import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as feedbackApi from '@/api/inspectionFeedback'
import type {
  FeedbackItem,
  FeedbackStatus,
  CuratePayload,
  DefectLibrarySummary,
} from '@/api/inspectionFeedback'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

export const useInspectionFeedbackStore = defineStore('inspectionFeedback', () => {
  const items = ref<FeedbackItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const library = ref<DefectLibrarySummary | null>(null)

  const libraryTotal = computed(() =>
    (library.value?.classes ?? []).reduce((sum, c) => sum + c.count, 0),
  )

  const newCount = computed(() => items.value.filter((f) => f.status === 'new').length)
  const escapeCount = computed(
    () => items.value.filter((f) => f.operator_mark === 'escape').length,
  )
  const overkillCount = computed(
    () => items.value.filter((f) => f.operator_mark === 'overkill').length,
  )

  async function fetchAll(status?: FeedbackStatus): Promise<void> {
    loading.value = true
    error.value = null
    try {
      items.value = await feedbackApi.listFeedback(status)
    } catch (err) {
      error.value = extractMessage(err, 'Gagal memuat umpan balik inspeksi')
    } finally {
      loading.value = false
    }
  }

  async function fetchLibrary(projectId?: string): Promise<void> {
    try {
      library.value = await feedbackApi.getDefectLibrarySummary(projectId)
    } catch (err) {
      error.value = extractMessage(err, 'Gagal memuat pustaka cacat')
    }
  }

  async function curate(feedbackId: string, body: CuratePayload): Promise<void> {
    const prev = items.value
    items.value = items.value.map((f) =>
      f.id === feedbackId
        ? {
            ...f,
            operator_mark: body.operator_mark ?? f.operator_mark,
            status: body.status ?? f.status,
          }
        : f,
    )
    try {
      const updated = await feedbackApi.curateFeedback(feedbackId, body)
      items.value = items.value.map((f) => (f.id === feedbackId ? updated : f))
    } catch (err) {
      items.value = prev
      error.value = extractMessage(err, 'Gagal memperbarui umpan balik')
      throw err
    }
  }

  async function promote(feedbackId: string): Promise<void> {
    const prev = items.value
    items.value = items.value.map((f) =>
      f.id === feedbackId ? { ...f, status: 'promoted' as const } : f,
    )
    try {
      await feedbackApi.promoteFeedback(feedbackId)
    } catch (err) {
      items.value = prev
      error.value = extractMessage(err, 'Gagal mempromosikan contoh cacat')
      throw err
    }
  }

  return {
    items,
    loading,
    error,
    library,
    libraryTotal,
    newCount,
    escapeCount,
    overkillCount,
    fetchAll,
    fetchLibrary,
    curate,
    promote,
  }
})
