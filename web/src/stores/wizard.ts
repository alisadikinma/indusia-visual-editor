import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as projectsApi from '@/api/projects'
import * as assetsApi from '@/api/assets'
import * as bomApi from '@/api/bom'
import type { Project } from '@/api/projects'
import type { Asset, AssetKind } from '@/api/assets'
import type { BomItem } from '@/api/bom'

type StepKey = 'project' | 'bom' | 'golden' | 'drawing' | 'review'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

function slugify(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64)
}

export const useWizardStore = defineStore('wizard', () => {
  const steps: StepKey[] = ['project', 'bom', 'golden', 'drawing', 'review']
  const stepIndex = ref(0)

  const project = ref<Project | null>(null)
  const draftName = ref('')
  const draftSlug = ref('')

  const assets = ref<Partial<Record<AssetKind, Asset>>>({})
  const bomItems = ref<BomItem[]>([])

  const busy = ref(false)
  const error = ref<string | null>(null)

  const currentStep = computed<StepKey>(() => steps[stepIndex.value])
  const isFirst = computed(() => stepIndex.value === 0)
  const isLast = computed(() => stepIndex.value === steps.length - 1)
  const projectId = computed(() => project.value?.id ?? null)

  const canAdvance = computed<boolean>(() => {
    switch (currentStep.value) {
      case 'project':
        return draftName.value.trim().length > 0 && draftSlug.value.trim().length > 0
      case 'bom':
        return assets.value.bom != null
      case 'golden':
        // Top side mandatory, bottom side optional. Most single-side
        // PCBs (LED strips, simple sensor boards) have no through-hole
        // components on the bottom to inspect.
        return assets.value.golden_top != null
      case 'drawing':
        return assets.value.drawing != null
      case 'review':
        return true
      default:
        return false
    }
  })

  function reset() {
    stepIndex.value = 0
    project.value = null
    draftName.value = ''
    draftSlug.value = ''
    assets.value = {}
    bomItems.value = []
    busy.value = false
    error.value = null
  }

  function hydrateFromExisting(p: Project) {
    project.value = p
    draftName.value = p.name
    draftSlug.value = p.slug
  }

  function autofillSlug() {
    if (!draftSlug.value && draftName.value) {
      draftSlug.value = slugify(draftName.value)
    }
  }

  async function createProject(): Promise<void> {
    busy.value = true
    error.value = null
    try {
      const created = await projectsApi.createProject({
        name: draftName.value.trim(),
        slug: draftSlug.value.trim(),
      })
      project.value = created
    } catch (err) {
      error.value = extractMessage(err, 'Failed to create project')
      throw err
    } finally {
      busy.value = false
    }
  }

  async function uploadAsset(kind: AssetKind, file: File): Promise<void> {
    if (!project.value) throw new Error('Project not created yet')
    busy.value = true
    error.value = null
    try {
      const uploaded = await assetsApi.uploadAsset(project.value.id, kind, file)
      assets.value = { ...assets.value, [kind]: uploaded }
    } catch (err) {
      error.value = extractMessage(err, 'Upload failed')
      throw err
    } finally {
      busy.value = false
    }
  }

  async function fetchBomItems(): Promise<void> {
    if (!project.value) return
    try {
      bomItems.value = await bomApi.listBomItems(project.value.id)
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load BOM items')
    }
  }

  async function next(): Promise<void> {
    if (currentStep.value === 'project' && !project.value) {
      await createProject()
    }
    if (currentStep.value === 'bom') {
      await fetchBomItems()
    }
    if (!isLast.value) stepIndex.value++
  }

  function back() {
    if (!isFirst.value) stepIndex.value--
  }

  return {
    steps,
    stepIndex,
    currentStep,
    isFirst,
    isLast,
    project,
    projectId,
    draftName,
    draftSlug,
    assets,
    bomItems,
    busy,
    error,
    canAdvance,
    reset,
    hydrateFromExisting,
    autofillSlug,
    createProject,
    uploadAsset,
    fetchBomItems,
    next,
    back,
  }
})
