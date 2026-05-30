<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useInspectionFeedbackStore } from '@/stores/inspectionFeedback'
import { useToastStore } from '@/stores/toast'
import AppButton from '@/components/primitives/AppButton.vue'
import type { FeedbackItem, FeedbackStatus, OperatorMark } from '@/api/inspectionFeedback'

const { t, locale } = useI18n()
const store = useInspectionFeedbackStore()
const toast = useToastStore()

const filter = ref<FeedbackStatus | 'all'>('all')

const filters: Array<{ key: FeedbackStatus | 'all'; labelKey: string }> = [
  { key: 'all', labelKey: 'feedback.filterAll' },
  { key: 'new', labelKey: 'feedback.filterNew' },
  { key: 'curated', labelKey: 'feedback.filterCurated' },
  { key: 'promoted', labelKey: 'feedback.filterPromoted' },
  { key: 'dismissed', labelKey: 'feedback.filterDismissed' },
]

const visibleItems = computed(() =>
  filter.value === 'all'
    ? store.items
    : store.items.filter((f) => f.status === filter.value),
)

onMounted(() => store.fetchAll())

function applyFilter(key: FeedbackStatus | 'all') {
  filter.value = key
}

const verdictTone: Record<FeedbackItem['model_verdict'], string> = {
  pass: 'bg-primary-50 text-primary-800',
  fail: 'bg-red-50 text-red-700',
  uncertain: 'bg-amber-50 text-amber-800',
}

const markTone: Record<OperatorMark, string> = {
  confirmed: 'bg-surface-raised text-ink-600',
  escape: 'bg-red-50 text-red-700',
  overkill: 'bg-amber-50 text-amber-800',
}

function isResolved(row: FeedbackItem): boolean {
  return row.status === 'promoted' || row.status === 'dismissed' || row.operator_mark != null
}

function fmtTime(iso: string | null): string {
  if (!iso) return t('feedback.neverTs')
  try {
    return new Intl.DateTimeFormat(locale.value, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(iso))
  } catch {
    return iso.slice(0, 16)
  }
}

async function mark(row: FeedbackItem, operatorMark: OperatorMark) {
  try {
    await store.curate(row.id, { operator_mark: operatorMark, status: 'curated' })
    toast.success(t('feedback.curateSuccess'))
  } catch {
    toast.error(t('feedback.curateFailed'), store.error ?? undefined)
  }
}

async function promote(row: FeedbackItem) {
  try {
    await store.promote(row.id)
    toast.success(t('feedback.promoteSuccess'))
  } catch {
    toast.error(t('feedback.promoteFailed'), store.error ?? undefined)
  }
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <header>
      <p class="text-[11px] font-mono uppercase tracking-wider text-ink-400">
        {{ t('feedback.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('feedback.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('feedback.subhead') }}</p>
    </header>

    <section
      data-testid="feedback-banner"
      class="rounded-xl border border-border-default bg-surface-raised p-5 space-y-2"
    >
      <h2 class="text-sm font-semibold text-ink-900">{{ t('feedback.bannerTitle') }}</h2>
      <p class="text-sm text-ink-700">
        <span class="inline-flex items-center h-5 px-2 mr-2 rounded-full text-[11px] font-mono bg-primary-50 text-primary-800">v1</span>
        {{ t('feedback.bannerManual') }}
      </p>
      <p class="text-sm text-ink-500">
        <span class="inline-flex items-center h-5 px-2 mr-2 rounded-full text-[11px] font-mono bg-engineer-100 text-engineer-700">v1.5</span>
        {{ t('feedback.bannerLive') }}
      </p>
    </section>

    <div class="flex items-center gap-2 flex-wrap">
      <button
        v-for="f in filters"
        :key="f.key"
        type="button"
        :data-testid="`feedback-filter-${f.key}`"
        :data-active="filter === f.key ? 'true' : 'false'"
        class="h-8 px-3 rounded-full text-xs font-medium transition border"
        :class="
          filter === f.key
            ? 'bg-primary-700 text-white border-primary-700'
            : 'bg-white text-ink-700 border-border-default hover:bg-ink-100'
        "
        @click="applyFilter(f.key)"
      >
        {{ t(f.labelKey) }}
      </button>
      <span class="ml-auto text-xs text-ink-500">
        {{
          t('feedback.summary', {
            total: store.items.length,
            newCount: store.newCount,
            escape: store.escapeCount,
            overkill: store.overkillCount,
          })
        }}
      </span>
    </div>

    <div
      data-testid="feedback-table"
      class="rounded-xl bg-white border border-border-default shadow-card overflow-hidden"
    >
      <table class="w-full text-sm">
        <thead class="bg-surface-raised text-[11px] font-mono uppercase tracking-wider text-ink-500">
          <tr>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('feedback.colTime') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('feedback.colBoard') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('feedback.colVerdict') }}</th>
            <th class="text-left px-4 py-2.5 font-medium">{{ t('feedback.colNote') }}</th>
            <th class="text-right px-4 py-2.5 font-medium">{{ t('feedback.colAction') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="store.loading" class="border-t border-border-subtle">
            <td colspan="5" class="px-4 py-10 text-center text-sm text-ink-500">{{ t('common.loading') }}</td>
          </tr>
          <tr v-else-if="visibleItems.length === 0" class="border-t border-border-subtle">
            <td colspan="5" class="px-4 py-10 text-center text-sm text-ink-500">{{ t('feedback.empty') }}</td>
          </tr>
          <tr
            v-for="row in visibleItems"
            v-else
            :key="row.id"
            data-testid="feedback-row"
            class="border-t border-border-subtle"
          >
            <td class="px-4 py-3 text-xs font-mono text-ink-600 whitespace-nowrap">
              {{ fmtTime(row.inspection_ts) }}
            </td>
            <td class="px-4 py-3">
              <p class="font-mono font-medium text-ink-900">
                {{ row.designator ?? t('feedback.noDesignator') }}
              </p>
              <p v-if="row.edge_id" class="text-xs font-mono text-ink-500">{{ row.edge_id }}</p>
            </td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                :class="verdictTone[row.model_verdict]"
              >
                {{ t(`feedback.verdict.${row.model_verdict}`) }}
              </span>
            </td>
            <td class="px-4 py-3">
              <span
                v-if="row.operator_mark"
                class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                :class="markTone[row.operator_mark]"
              >
                {{ t(`feedback.mark.${row.operator_mark}`) }}
              </span>
              <span v-else class="text-xs text-ink-400">—</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center justify-end gap-2">
                <span
                  v-if="row.status === 'promoted' || row.status === 'dismissed'"
                  data-testid="feedback-resolved"
                  class="inline-flex items-center h-6 px-2.5 rounded-full text-[11px] font-medium bg-primary-50 text-primary-800"
                >
                  {{ t('feedback.resolved') }}
                </span>
                <template v-else>
                  <button
                    type="button"
                    :data-testid="`feedback-escape-${row.id}`"
                    :title="t('feedback.actionEscapeHint')"
                    class="h-8 px-3 rounded-md text-xs font-medium border transition"
                    :class="
                      row.operator_mark === 'escape'
                        ? 'bg-red-50 text-red-700 border-red-200'
                        : 'bg-white text-ink-700 border-border-default hover:bg-ink-100'
                    "
                    @click="mark(row, 'escape')"
                  >
                    {{ t('feedback.actionEscape') }}
                  </button>
                  <button
                    type="button"
                    :data-testid="`feedback-overkill-${row.id}`"
                    :title="t('feedback.actionOverkillHint')"
                    class="h-8 px-3 rounded-md text-xs font-medium border transition"
                    :class="
                      row.operator_mark === 'overkill'
                        ? 'bg-amber-50 text-amber-800 border-amber-200'
                        : 'bg-white text-ink-700 border-border-default hover:bg-ink-100'
                    "
                    @click="mark(row, 'overkill')"
                  >
                    {{ t('feedback.actionOverkill') }}
                  </button>
                  <AppButton
                    v-if="isResolved(row) && row.operator_mark === 'escape'"
                    :data-testid="`feedback-promote-${row.id}`"
                    size="sm"
                    variant="primary"
                    :title="t('feedback.promoteHint')"
                    @click="promote(row)"
                  >
                    {{ t('feedback.promote') }}
                  </AppButton>
                </template>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
