<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api/client'

const { t, locale } = useI18n()

interface ModelRow {
  id: string
  project_name: string
  pcb_name: string
  version: string
  sha256: string
  size_mb: number
  promoted_at: string
  pinned_edges: number
  status: 'production' | 'staged' | 'archived'
}

const items = ref<ModelRow[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await apiClient.get<{ data: ModelRow[] }>('/models')
    items.value = data.data
  } finally {
    loading.value = false
  }
})

const filter = ref<'all' | 'production' | 'staged' | 'archived'>('all')
const filtered = computed(() =>
  filter.value === 'all' ? items.value : items.value.filter((m) => m.status === filter.value),
)

const statusTone: Record<string, string> = {
  production: 'bg-primary-50 text-primary-800',
  staged: 'bg-blue-50 text-blue-700',
  archived: 'bg-ink-100 text-ink-600',
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
    <header class="flex items-end justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-semibold text-ink-900">{{ t('models.title') }}</h1>
        <p class="text-sm text-ink-500">{{ t('models.summary', { n: items.length }) }}</p>
      </div>
      <div class="inline-flex items-center rounded-full border border-border-default bg-white p-0.5 text-xs font-medium">
        <button
          v-for="opt in (['all', 'production', 'staged', 'archived'] as const)"
          :key="opt"
          type="button"
          class="h-8 px-3 rounded-full transition"
          :class="filter === opt ? 'bg-ink-900 text-white' : 'text-ink-500 hover:text-ink-900'"
          @click="filter = opt"
        >
          {{ t(`models.filter.${opt}`) }}
        </button>
      </div>
    </header>

    <div data-testid="models-table" class="rounded-xl bg-white border border-border-default shadow-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-raised text-[11px] font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colVersion') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colProject') }}</th>
            <th class="text-left px-4 py-3 font-medium">SHA</th>
            <th class="text-right px-4 py-3 font-medium">{{ t('models.colSize') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colStatus') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colPromoted') }}</th>
            <th class="text-right px-4 py-3 font-medium">{{ t('models.colPinned') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" class="border-t border-border-subtle">
            <td colspan="7" class="px-4 py-6 text-center text-sm text-ink-500">{{ t('common.loading') }}</td>
          </tr>
          <tr v-else-if="filtered.length === 0" class="border-t border-border-subtle">
            <td colspan="7" class="px-4 py-10 text-center text-sm text-ink-500">{{ t('models.empty') }}</td>
          </tr>
          <tr v-for="m in filtered" :key="m.id" class="border-t border-border-subtle">
            <td class="px-4 py-3 font-mono font-medium text-ink-900">{{ m.version }}</td>
            <td class="px-4 py-3">
              <p class="font-medium text-ink-900">{{ m.project_name }}</p>
              <p class="text-xs font-mono text-ink-500">{{ m.pcb_name }}</p>
            </td>
            <td class="px-4 py-3 font-mono text-xs text-ink-500">{{ m.sha256.slice(0, 7) }}…{{ m.sha256.slice(-4) }}</td>
            <td class="px-4 py-3 text-right font-mono tabular-nums">{{ m.size_mb }} MB</td>
            <td class="px-4 py-3">
              <span class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-semibold uppercase tracking-wide" :class="statusTone[m.status]">
                {{ t(`models.status.${m.status}`) }}
              </span>
            </td>
            <td class="px-4 py-3 text-xs text-ink-500 font-mono">{{ fmtDate(m.promoted_at) }}</td>
            <td class="px-4 py-3 text-right font-mono tabular-nums text-ink-700">{{ m.pinned_edges }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
