import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as deployApi from '@/api/deploy'
import type { Deployment } from '@/api/deploy'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

export const useDeployStore = defineStore('deploy', () => {
  const current = ref<Deployment | null>(null)
  const history = ref<Deployment[]>([])
  const promoting = ref(false)
  const error = ref<string | null>(null)

  async function promote(projectId: string): Promise<Deployment | null> {
    promoting.value = true
    error.value = null
    try {
      current.value = await deployApi.promoteToProduction(projectId)
      return current.value
    } catch (err) {
      error.value = extractMessage(err, 'Failed to promote model')
      return null
    } finally {
      promoting.value = false
    }
  }

  async function loadHistory(projectId: string): Promise<void> {
    try {
      history.value = await deployApi.listDeployments(projectId)
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load deployments')
    }
  }

  function reset() {
    current.value = null
    history.value = []
    promoting.value = false
    error.value = null
  }

  return { current, history, promoting, error, promote, loadHistory, reset }
})
