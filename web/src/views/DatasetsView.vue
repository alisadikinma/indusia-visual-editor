<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api/client'

const { t } = useI18n()

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
})

const kindTone: Record<string, string> = {
  training: 'bg-primary-50 border-primary-200 text-primary-800',
  holdout: 'bg-info/10 border-info/30 text-info',
  production_run: 'bg-amber-50 border-amber-200 text-amber-800',
}
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('datasets.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('datasets.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('datasets.subhead') }}</p>
    </header>

    <div class="rounded-xl bg-white border border-ink-200 shadow-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-3 font-medium">{{ t('datasets.colName') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('datasets.colProject') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('datasets.colKind') }}</th>
            <th class="text-right px-4 py-3 font-medium">{{ t('datasets.colRegions') }}</th>
            <th class="text-right px-4 py-3 font-medium">{{ t('datasets.colSize') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('datasets.colCreated') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" class="border-t border-ink-100">
            <td colspan="6" class="px-4 py-6 text-center text-sm text-ink-500">
              {{ t('common.loading') }}
            </td>
          </tr>
          <tr v-else-if="items.length === 0" class="border-t border-ink-100">
            <td colspan="6" class="px-4 py-10 text-center text-sm text-ink-500">
              {{ t('datasets.empty') }}
            </td>
          </tr>
          <tr v-for="row in items" :key="row.id" class="border-t border-ink-100">
            <td class="px-4 py-3 font-medium text-ink-900">{{ row.name }}</td>
            <td class="px-4 py-3 font-mono text-xs text-ink-500">{{ row.project }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center h-5 px-2 rounded-full border text-[11px] font-medium"
                :class="kindTone[row.kind]"
              >
                {{ t(`datasets.kind.${row.kind}`) }}
              </span>
            </td>
            <td class="px-4 py-3 text-right font-mono tabular-nums">{{ row.region_count }}</td>
            <td class="px-4 py-3 text-right font-mono tabular-nums">{{ row.size_mb }} MB</td>
            <td class="px-4 py-3 text-xs text-ink-500 font-mono">
              {{ new Date(row.created_at).toISOString().slice(0, 10) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
