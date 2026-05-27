import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as edgesApi from '@/api/edges'
import type { Edge } from '@/api/edges'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

export const useEdgesStore = defineStore('edges', () => {
  const items = ref<Edge[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const onlineCount = computed(() => {
    const cutoff = Date.now() - 5 * 60_000
    return items.value.filter(
      (e) => e.last_seen_at && new Date(e.last_seen_at).getTime() >= cutoff,
    ).length
  })
  const offlineCount = computed(() => items.value.length - onlineCount.value)

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      items.value = await edgesApi.listEdges()
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load edges')
    } finally {
      loading.value = false
    }
  }

  async function unpin(edgeId: string): Promise<void> {
    try {
      const updated = await edgesApi.pinEdge(edgeId, null, null)
      items.value = items.value.map((e) => (e.id === edgeId ? updated : e))
    } catch (err) {
      error.value = extractMessage(err, 'Failed to unpin edge')
      throw err
    }
  }

  return { items, loading, error, onlineCount, offlineCount, fetchAll, unpin }
})
