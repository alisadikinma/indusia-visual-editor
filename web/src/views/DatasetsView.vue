<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { apiClient } from '@/api/client'
import { useInspectionFeedbackStore } from '@/stores/inspectionFeedback'

const { t, locale } = useI18n()

const feedbackStore = useInspectionFeedbackStore()
const { library, libraryTotal } = storeToRefs(feedbackStore)
const floorPct = (count: number): number =>
  Math.min(100, Math.round((count / (library.value?.floor ?? 100)) * 100))

interface DatasetRow {
  id: string
  name: string
  project: string
  region_count: number
  size_mb: number
  created_at: string
  kind: 'training' | 'holdout' | 'production_run'
}

const items = ref<DatasetRow[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await apiClient.get<{ data: DatasetRow[] }>('/datasets')
    items.value = data.data
  } finally {
    loading.value = false
  }
  await feedbackStore.fetchLibrary()
})

const totalRegions = computed(() => items.value.reduce((a, d) => a + d.region_count, 0))

const kindTone: Record<string, string> = {
  training: 'bg-primary-50 text-primary-800',
  holdout: 'bg-blue-50 text-blue-700',
  production_run: 'bg-amber-50 text-amber-800',
}

function fmtDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
  } catch {
    return iso.slice(0, 10)
  }
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <header>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('datasets.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('datasets.summary', { n: items.length, regions: totalRegions }) }}</p>
    </header>

    <section
      v-if="library"
      data-testid="defect-library"
      class="rounded-xl border border-border-default bg-white shadow-card p-5 space-y-4"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <h2 class="text-base font-semibold text-ink-900">{{ t('datasets.library.title') }}</h2>
          <p class="text-sm text-ink-500">
            {{ t('datasets.library.subhead', { total: libraryTotal }) }}
          </p>
        </div>
        <span class="inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 shrink-0">
          {{ t('datasets.library.notConsumed') }}
        </span>
      </div>
      <p class="text-xs text-ink-500">
        {{ t('datasets.library.floorNote', { floor: library.floor }) }}
      </p>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div
          v-for="c in library.classes"
          :key="c.defect_criterion"
          data-testid="defect-class"
          class="rounded-lg border border-border-subtle bg-surface-raised p-3"
        >
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-[11px] font-mono text-ink-600 truncate">{{ c.defect_criterion }}</span>
            <span class="text-lg font-semibold font-mono tabular-nums text-ink-900">{{ c.count }}</span>
          </div>
          <div class="mt-2 h-1.5 rounded-full bg-ink-100 overflow-hidden">
            <div
              class="h-full rounded-full"
              :class="c.meets_floor ? 'bg-primary-500' : 'bg-ink-300'"
              :style="{ width: `${floorPct(c.count)}%` }"
            />
          </div>
        </div>
      </div>
    </section>

    <div v-if="loading" class="rounded-xl border border-border-default bg-white px-5 py-16 text-center text-sm text-ink-500">
      {{ t('common.loading') }}
    </div>
    <div v-else-if="items.length === 0" class="rounded-xl border border-border-default bg-white px-5 py-16 text-center text-sm text-ink-500">
      {{ t('datasets.empty') }}
    </div>

    <div v-else data-testid="datasets-grid" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <article
        v-for="d in items"
        :key="d.id"
        data-testid="dataset-card"
        class="rounded-xl bg-white border border-border-default shadow-card p-5"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <h2 class="text-base font-semibold text-ink-900 truncate">{{ d.name }}</h2>
            <p class="text-xs font-mono text-ink-500 truncate">{{ d.project }}</p>
          </div>
          <span class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium shrink-0" :class="kindTone[d.kind]">
            {{ t(`datasets.kind.${d.kind}`) }}
          </span>
        </div>
        <dl class="mt-4 grid grid-cols-3 gap-3">
          <div>
            <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('datasets.colRegions') }}</dt>
            <dd class="text-lg font-semibold font-mono tabular-nums text-ink-900">{{ d.region_count }}</dd>
          </div>
          <div>
            <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('datasets.colSize') }}</dt>
            <dd class="text-lg font-semibold font-mono tabular-nums text-ink-900">{{ d.size_mb }} MB</dd>
          </div>
          <div>
            <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('datasets.colCreated') }}</dt>
            <dd class="text-sm font-mono text-ink-700 mt-1">{{ fmtDate(d.created_at) }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </div>
</template>
