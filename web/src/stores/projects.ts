import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as projectsApi from '@/api/projects'
import { getDashboardSummary, type DashboardSummary } from '@/api/dashboard'
import type { Project, ProjectStatus } from '@/api/projects'

export const useProjectsStore = defineStore('projects', () => {
  const items = ref<Project[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Bundle 2.1 — DashboardView reads the richer cross-project rollup
  // (bom_count + latest_map per project) from GET /api/dashboard/summary.
  const summary = ref<DashboardSummary | null>(null)
  const summaryLoading = ref(false)

  const count = computed(() => items.value.length)
  const byStatus = (status: ProjectStatus) => items.value.filter((p) => p.status === status)
  const drafting = computed(() => byStatus('drafting'))
  const training = computed(() => byStatus('training'))
  const deployed = computed(() => byStatus('deployed'))

  async function fetchAll(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      items.value = await projectsApi.listProjects()
    } catch (err) {
      const e = err as { message?: string }
      error.value = e?.message ?? 'Failed to load projects'
    } finally {
      loading.value = false
    }
  }

  async function fetchSummary(): Promise<void> {
    summaryLoading.value = true
    error.value = null
    try {
      summary.value = await getDashboardSummary()
    } catch (err) {
      const e = err as { message?: string }
      error.value = e?.message ?? 'Failed to load dashboard'
    } finally {
      summaryLoading.value = false
    }
  }

  async function create(payload: { name: string; slug: string }): Promise<Project> {
    const created = await projectsApi.createProject(payload)
    items.value = [created, ...items.value]
    return created
  }

  return {
    items,
    loading,
    error,
    summary,
    summaryLoading,
    count,
    drafting,
    training,
    deployed,
    fetchAll,
    fetchSummary,
    create,
  }
})
