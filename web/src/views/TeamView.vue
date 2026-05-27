<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api/client'

const { t } = useI18n()

interface TeamMember {
  id: string
  email: string
  role: 'admin' | 'engineer' | 'viewer'
  last_active_at: string | null
  created_at: string
}

const items = ref<TeamMember[]>([])
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await apiClient.get<{ data: TeamMember[] }>('/team')
    items.value = data.data
  } finally {
    loading.value = false
  }
})

const roleTone: Record<string, string> = {
  admin: 'bg-primary-50 border-primary-200 text-primary-800',
  engineer: 'bg-engineer-50 border-engineer-200 text-engineer-800',
  viewer: 'bg-ink-100 border-ink-200 text-ink-600',
}
</script>

<template>
  <div class="p-8 max-w-[1100px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('team.kicker') }}</p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('team.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('team.subhead') }}</p>
    </header>

    <div class="rounded-xl bg-white border border-ink-200 shadow-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colEmail') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colRole') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colLastActive') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colCreated') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" class="border-t border-ink-100">
            <td colspan="4" class="px-4 py-6 text-center text-sm text-ink-500">
              {{ t('common.loading') }}
            </td>
          </tr>
          <tr v-else-if="items.length === 0" class="border-t border-ink-100">
            <td colspan="4" class="px-4 py-10 text-center text-sm text-ink-500">
              {{ t('team.empty') }}
            </td>
          </tr>
          <tr v-for="m in items" :key="m.id" class="border-t border-ink-100">
            <td class="px-4 py-3 font-medium text-ink-900">{{ m.email }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center h-5 px-2 rounded-full border text-[11px] font-medium"
                :class="roleTone[m.role]"
              >
                {{ t(`team.role.${m.role}`) }}
              </span>
            </td>
            <td class="px-4 py-3 text-xs text-ink-500 font-mono">
              {{ m.last_active_at ? new Date(m.last_active_at).toLocaleString() : t('team.neverActive') }}
            </td>
            <td class="px-4 py-3 text-xs text-ink-500 font-mono">
              {{ new Date(m.created_at).toISOString().slice(0, 10) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
