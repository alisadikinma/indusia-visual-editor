<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { apiClient } from '@/api/client'

const { t, locale } = useI18n()

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
  admin: 'bg-primary-50 text-primary-800',
  engineer: 'bg-engineer-50 text-engineer-800',
  viewer: 'bg-ink-100 text-ink-600',
}

function displayName(email: string): string {
  const local = email.split('@')[0]
  return local
    .split(/[._-]/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}
function initials(email: string): string {
  return displayName(email)
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}
function lastActive(iso: string | null): string {
  if (!iso) return t('team.neverActive')
  try {
    return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
  } catch {
    return iso.slice(0, 10)
  }
}
const avatarTones = ['bg-primary-600', 'bg-blue-500', 'bg-amber-500', 'bg-red-500', 'bg-engineer-600', 'bg-ink-500']
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('team.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('team.summary', { n: items.length }) }}</p>
    </header>

    <div data-testid="team-table" class="rounded-xl bg-white border border-border-default shadow-card overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-surface-raised text-[11px] font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colMember') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colEmail') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colRole') }}</th>
            <th class="text-left px-4 py-3 font-medium">{{ t('team.colLastActive') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" class="border-t border-border-subtle">
            <td colspan="4" class="px-4 py-6 text-center text-sm text-ink-500">{{ t('common.loading') }}</td>
          </tr>
          <tr v-else-if="items.length === 0" class="border-t border-border-subtle">
            <td colspan="4" class="px-4 py-10 text-center text-sm text-ink-500">{{ t('team.empty') }}</td>
          </tr>
          <tr v-for="(m, i) in items" :key="m.id" class="border-t border-border-subtle">
            <td class="px-4 py-3">
              <div class="flex items-center gap-3">
                <span class="h-9 w-9 grid place-items-center rounded-full text-white text-xs font-semibold shrink-0" :class="avatarTones[i % avatarTones.length]">
                  {{ initials(m.email) }}
                </span>
                <span class="font-medium text-ink-900">{{ displayName(m.email) }}</span>
              </div>
            </td>
            <td class="px-4 py-3 font-mono text-xs text-ink-500">{{ m.email }}</td>
            <td class="px-4 py-3">
              <span class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium" :class="roleTone[m.role]">
                {{ t(`team.role.${m.role}`) }}
              </span>
            </td>
            <td class="px-4 py-3 text-xs text-ink-500 font-mono">{{ lastActive(m.last_active_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
