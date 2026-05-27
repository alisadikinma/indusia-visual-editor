<script setup lang="ts">
import { computed, onMounted } from 'vue'
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

async function unpin(id: string) {
  try {
    await edges.unpin(id)
    toast.success(t('edges.unpinSuccess'))
  } catch {
    toast.error(t('edges.unpinFailed'), edges.error ?? undefined)
  }
}

const summary = computed(() => ({
  total: edges.items.length,
  online: edges.onlineCount,
  offline: edges.offlineCount,
  pinned: edges.items.filter((e) => e.version_policy.mode === 'pinned').length,
}))
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('edges.kicker') }}</p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('edges.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('edges.subhead') }}</p>
    </header>

    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('edges.statTotal') }}</p>
        <p class="mt-1 text-3xl font-semibold font-mono tabular-nums text-ink-900">{{ summary.total }}</p>
      </div>
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-success">{{ t('edges.statOnline') }}</p>
        <p class="mt-1 text-3xl font-semibold font-mono tabular-nums text-success">{{ summary.online }}</p>
      </div>
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('edges.statOffline') }}</p>
        <p class="mt-1 text-3xl font-semibold font-mono tabular-nums text-ink-900">{{ summary.offline }}</p>
      </div>
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-warning">{{ t('edges.statPinned') }}</p>
        <p class="mt-1 text-3xl font-semibold font-mono tabular-nums text-warning">{{ summary.pinned }}</p>
      </div>
    </div>

    <div class="rounded-xl bg-white border border-ink-200 shadow-card overflow-hidden">
      <header class="flex items-center justify-between px-4 py-3 border-b border-ink-200">
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
        <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colName') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colWebhook') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colPolicy') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('edges.colState') }}</th>
            <th class="text-right px-4 py-2.5 font-medium" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="edges.items.length === 0" class="border-t border-ink-100">
            <td colspan="5" class="px-4 py-10 text-center text-sm text-ink-500">
              {{ t('edges.empty') }}
            </td>
          </tr>
          <tr v-for="edge in edges.items" :key="edge.id" class="border-t border-ink-100">
            <td class="px-4 py-3">
              <p class="font-medium text-ink-900">{{ edge.name }}</p>
              <p class="text-xs font-mono text-ink-500">
                {{ edge.last_seen_at ? new Date(edge.last_seen_at).toLocaleString() : t('edges.neverSeen') }}
              </p>
            </td>
            <td class="px-4 py-3 font-mono text-xs text-ink-700 max-w-xs truncate">
              {{ edge.webhook_url }}
            </td>
            <td class="px-4 py-3 font-mono text-xs">
              <span v-if="edge.version_policy.mode === 'pinned'" class="text-warning">
                {{ t('edges.pinned') }} · {{ edge.version_policy.pinned_model }}@{{ edge.version_policy.pinned_version }}
              </span>
              <span v-else class="text-ink-700">auto_pull_latest</span>
            </td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                :class="
                  isOnline(edge.last_seen_at)
                    ? 'bg-success/10 text-success'
                    : 'bg-ink-100 text-ink-500'
                "
              >
                ● {{ isOnline(edge.last_seen_at) ? t('edges.online') : t('edges.offline') }}
              </span>
            </td>
            <td class="px-4 py-3 text-right">
              <AppButton
                v-if="edge.version_policy.mode === 'pinned'"
                size="sm"
                variant="ghost"
                @click="unpin(edge.id)"
              >
                {{ t('edges.unpin') }}
              </AppButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
