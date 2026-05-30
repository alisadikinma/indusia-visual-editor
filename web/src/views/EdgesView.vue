<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useEdgesStore } from '@/stores/edges'
import { useToastStore } from '@/stores/toast'
import AppButton from '@/components/primitives/AppButton.vue'

const { t } = useI18n()
const edges = useEdgesStore()
const toast = useToastStore()

onMounted(() => edges.fetchAll())

function isOnline(lastSeenAt: string | null): boolean {
  return lastSeenAt != null && new Date(lastSeenAt).getTime() >= Date.now() - 5 * 60_000
}

function heartbeat(lastSeenAt: string | null): string {
  if (!lastSeenAt) return t('edges.neverSeen')
  const sec = Math.round((Date.now() - new Date(lastSeenAt).getTime()) / 1000)
  if (sec < 60) return t('edges.secondsAgo', { n: sec })
  const min = Math.round(sec / 60)
  if (min < 60) return t('edges.minutesAgo', { n: min })
  const hr = Math.round(min / 60)
  if (hr < 24) return t('edges.hoursAgo', { n: hr })
  return t('edges.daysAgo', { n: Math.round(hr / 24) })
}

async function unpin(id: string) {
  try {
    await edges.unpin(id)
    toast.success(t('edges.unpinSuccess'))
  } catch {
    toast.error(t('edges.unpinFailed'), edges.error ?? undefined)
  }
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <header>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('edges.title') }}</h1>
      <p class="text-sm text-ink-500">
        {{ t('edges.summary', { total: edges.items.length, online: edges.onlineCount, offline: edges.offlineCount }) }}
      </p>
    </header>

    <div data-testid="edges-table" class="rounded-xl bg-white border border-border-default shadow-card overflow-hidden">
      <header class="flex items-center justify-between px-4 py-3 border-b border-border-default">
        <h2 class="text-base font-semibold text-ink-900">{{ t('edges.registry') }}</h2>
        <button
          type="button"
          class="text-xs font-mono text-ink-500 hover:text-ink-900"
          :disabled="edges.loading"
          @click="edges.fetchAll()"
        >
          {{ edges.loading ? t('common.loading') : t('common.refresh') }}
        </button>
      </header>
      <table class="w-full text-sm">
        <thead class="bg-surface-raised text-[11px] font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colName') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colState') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colHeartbeat') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colPolicy') }}</th>
            <th class="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="edges.items.length === 0" class="border-t border-border-subtle">
            <td colspan="5" class="px-4 py-10 text-center text-sm text-ink-500">{{ t('edges.empty') }}</td>
          </tr>
          <tr v-for="edge in edges.items" :key="edge.id" class="border-t border-border-subtle">
            <td class="px-4 py-3">
              <p class="font-mono font-medium text-ink-900">{{ edge.name }}</p>
              <p class="text-xs font-mono text-ink-500 truncate max-w-xs">{{ edge.webhook_url }}</p>
            </td>
            <td class="px-4 py-3">
              <span class="inline-flex items-center gap-1.5 text-xs font-medium" :class="isOnline(edge.last_seen_at) ? 'text-primary-700' : 'text-red-600'">
                <span class="h-1.5 w-1.5 rounded-full" :class="isOnline(edge.last_seen_at) ? 'bg-primary-500' : 'bg-red-500'" />
                {{ isOnline(edge.last_seen_at) ? t('edges.online') : t('edges.offline') }}
              </span>
            </td>
            <td class="px-4 py-3 text-xs font-mono" :class="isOnline(edge.last_seen_at) ? 'text-ink-500' : 'text-red-600'">
              {{ heartbeat(edge.last_seen_at) }}
            </td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-mono"
                :class="edge.version_policy.mode === 'pinned' ? 'bg-amber-50 text-amber-700' : 'bg-surface-raised text-ink-600'"
              >
                {{ edge.version_policy.mode === 'pinned' ? `pinned · ${edge.version_policy.pinned_version}` : 'auto-pull' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right">
              <AppButton v-if="edge.version_policy.mode === 'pinned'" size="sm" variant="secondary" @click="unpin(edge.id)">
                {{ t('edges.unpin') }}
              </AppButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
