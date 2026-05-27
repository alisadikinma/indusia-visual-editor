<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api/client'

const { t } = useI18n()

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
  production: 'bg-primary-50 border-primary-200 text-primary-800',
  staged: 'bg-amber-50 border-amber-200 text-amber-800',
  archived: 'bg-ink-100 border-ink-200 text-ink-600',
}
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('models.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('models.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('models.subhead') }}</p>
    </header>

    <div class="inline-flex items-center rounded-full border border-ink-200 bg-white p-0.5 text-xs font-mono">
      <button
        v-for="opt in (['all', 'production', 'staged', 'archived'] as const)"
        :key="opt"
        type="button"
        class="h-8 px-3 rounded-full capitalize transition"
        :class="filter === opt ? 'bg-ink-900 text-white' : 'text-ink-500 hover:text-ink-900'"
        @click="filter = opt"
      >
        {{ t(`models.filter.${opt}`) }}
      </button>
    </div>

    <div class="rounded-xl bg-white border border-ink-200 shadow-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colProject') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colVersion') }}</th>
            <th class="text-left px-4 py-3 font-medium">SHA</th>
            <th class="text-right px-4 py-3 font-medium">{{ t('models.colSize') }}</th>
            <th class="text-right px-4 py-3 font-medium">{{ t('models.colPinned') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colStatus') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('models.colPromoted') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" class="border-t border-ink-100">
            <td colspan="7" class="px-4 py-6 text-center text-sm text-ink-500">
              {{ t('common.loading') }}
            </td>
          </tr>
          <tr v-else-if="filtered.length === 0" class="border-t border-ink-100">
            <td colspan="7" class="px-4 py-10 text-center text-sm text-ink-500">
              {{ t('models.empty') }}
            </td>
          </tr>
          <tr v-for="m in filtered" :key="m.id" class="border-t border-ink-100">
            <td class="px-4 py-3">
              <p class="font-medium text-ink-900">{{ m.project_name }}</p>
              <p class="text-xs font-mono text-ink-500">{{ m.pcb_name }}</p>
            </td>
            <td class="px-4 py-3 font-mono">{{ m.version }}</td>
            <td class="px-4 py-3 font-mono text-xs text-ink-500">
              {{ m.sha256.slice(0, 7) }}…{{ m.sha256.slice(-4) }}
            </td>
            <td class="px-4 py-3 text-right font-mono tabular-nums">{{ m.size_mb }} MB</td>
            <td class="px-4 py-3 text-right font-mono tabular-nums">{{ m.pinned_edges }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center h-5 px-2 rounded-full border text-[11px] font-medium"
                :class="statusTone[m.status]"
              >
                {{ t(`models.status.${m.status}`) }}
              </span>
            </td>
            <td class="px-4 py-3 text-xs text-ink-500 font-mono">
              {{ new Date(m.promoted_at).toISOString().slice(0, 10) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
