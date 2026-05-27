import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as projectsApi from '@/api/projects'
import type { Project, ProjectStatus } from '@/api/projects'

export const useProjectsStore = defineStore('projects', () => {
  const items = ref<Project[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

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

  async function create(payload: { name: string; slug: string }): Promise<Project> {
    const created = await projectsApi.createProject(payload)
    items.value = [created, ...items.value]
    return created
  }

  return {
    items,
    loading,
    error,
    count,
    drafting,
    training,
    deployed,
    fetchAll,
    create,
  }
})
