<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

interface LsRegion {
  id?: string
  results?: Array<{
    type?: string
    value?: {
      x?: number
      y?: number
      width?: number
      height?: number
      rotation?: number
      rectanglelabels?: string[]
      labels?: string[]
    }
  }>
  value?: {
    x?: number
    y?: number
    width?: number
    height?: number
    rotation?: number
    rectanglelabels?: string[]
  }
  labels?: string[]
}

const props = defineProps<{ region: LsRegion | null }>()
const emit = defineEmits<{
  copy: []
  toggleVisible: []
  delete: []
  relate: []
  applyCriteria: [criteria: string[]]
}>()

const { t } = useI18n()

const tab = ref<'info' | 'history'>('info')

const value = computed(() => {
  const first = props.region?.results?.[0]?.value
  return first ?? props.region?.value ?? {}
})

const designator = computed<string>(() => {
  const labels =
    props.region?.results?.[0]?.value?.rectanglelabels ??
    props.region?.results?.[0]?.value?.labels ??
    props.region?.value?.rectanglelabels ??
    props.region?.labels ??
    []
  return labels[0] ?? ''
})

const regionId = computed<string>(() => props.region?.id ?? '')

function fmt(n: number | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toFixed(2)
}

const CRITERIA = [
  'missing_component',
  'orientation',
  'polarity_flip',
  'connector_pin_bending',
  'missing_pin_connector',
  'lifted_pin',
  'wrong_value',
  'misalignment',
] as const

const picked = ref<Record<string, boolean>>({})

// Reset the criteria selection whenever a different region is selected.
watch(
  () => props.region?.id,
  () => {
    picked.value = {}
    tab.value = 'info'
  },
)

function apply() {
  emit('applyCriteria', CRITERIA.filter((c) => picked.value[c]))
}

const GEO: { key: 'x' | 'y' | 'width' | 'height'; label: string }[] = [
  { key: 'x', label: 'X' },
  { key: 'y', label: 'Y' },
  { key: 'width', label: 'W' },
  { key: 'height', label: 'H' },
]

const ACTIONS = [
  { id: 'relate', tid: 'region-action-relate', icon: '+', labelKey: 'labeling.actionRelateShort' },
  { id: 'copy', tid: 'region-action-copy', icon: '⎘', labelKey: 'labeling.actionCopyShort' },
  { id: 'visible', tid: 'region-action-visible', icon: '👁', labelKey: 'labeling.actionVisibleShort' },
  { id: 'delete', tid: 'region-action-delete', icon: '🗑', labelKey: 'labeling.actionDeleteShort' },
] as const

function onAction(id: (typeof ACTIONS)[number]['id']) {
  if (id === 'relate') emit('relate')
  else if (id === 'copy') emit('copy')
  else if (id === 'visible') emit('toggleVisible')
  else emit('delete')
}
</script>

<template>
  <aside data-testid="region-panel" class="w-80 bg-white border-l border-border-default flex flex-col">
    <!-- Tabs -->
    <div class="flex items-center gap-1 px-4 pt-3 border-b border-border-default">
      <button
        type="button"
        data-testid="region-tab-info"
        class="h-9 px-3 text-sm font-medium rounded-t-md border-b-2 -mb-px transition"
        :class="tab === 'info' ? 'border-primary-500 text-primary-700' : 'border-transparent text-ink-500 hover:text-ink-900'"
        @click="tab = 'info'"
      >
        {{ t('labeling.tabInfo') }}
      </button>
      <button
        type="button"
        data-testid="region-tab-history"
        class="h-9 px-3 text-sm font-medium rounded-t-md border-b-2 -mb-px transition"
        :class="tab === 'history' ? 'border-primary-500 text-primary-700' : 'border-transparent text-ink-500 hover:text-ink-900'"
        @click="tab = 'history'"
      >
        {{ t('labeling.tabHistory') }}
      </button>
    </div>

    <!-- Empty -->
    <div
      v-if="!region"
      data-testid="region-empty"
      class="flex-1 grid place-items-center p-6 text-center"
    >
      <div class="space-y-2">
        <span class="mx-auto h-10 w-10 grid place-items-center rounded-full bg-ink-100 text-ink-400">↗</span>
        <p class="text-sm font-medium text-ink-700">{{ t('labeling.regionEmptyTitle') }}</p>
        <p class="text-xs text-ink-500">{{ t('labeling.regionEmptyHint') }}</p>
      </div>
    </div>

    <!-- History tab -->
    <div v-else-if="tab === 'history'" data-testid="region-history" class="flex-1 p-5">
      <p class="text-sm text-ink-500">{{ t('labeling.historyEmpty') }}</p>
    </div>

    <!-- Info tab -->
    <div v-else class="flex-1 overflow-y-auto p-5 space-y-5">
      <div class="flex items-center justify-between gap-2">
        <h3 class="text-base font-semibold text-ink-900">{{ designator || t('labeling.noSelection') }}</h3>
        <span class="text-[11px] font-mono text-ink-400 truncate max-w-[8rem]">
          {{ t('labeling.regionId') }} {{ regionId || '—' }}
        </span>
      </div>

      <section data-testid="region-geometry">
        <div class="grid grid-cols-4 gap-2 text-center">
          <div v-for="g in GEO" :key="g.key" class="rounded-md bg-surface-raised border border-border-subtle py-2">
            <p class="text-[10px] font-mono uppercase tracking-wider text-ink-400">{{ g.label }}</p>
            <p class="text-sm font-mono tabular-nums text-ink-900">{{ fmt(value[g.key]) }}</p>
          </div>
        </div>
        <div class="mt-2 rounded-md bg-surface-raised border border-border-subtle py-2 text-center">
          <p class="text-[10px] font-mono uppercase tracking-wider text-ink-400">R°</p>
          <p class="text-sm font-mono tabular-nums text-ink-900">{{ fmt(value.rotation) }}</p>
        </div>
        <p class="sr-only">{{ designator }}</p>
      </section>

      <section data-testid="region-criteria">
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500 mb-2">
          {{ t('labeling.criteria') }}
        </p>
        <ul class="space-y-1.5 text-sm">
          <li v-for="c in CRITERIA" :key="c" class="flex items-center gap-2">
            <input
              :id="`c-${c}`"
              v-model="picked[c]"
              type="checkbox"
              class="h-4 w-4 rounded border-ink-300 text-primary-600 focus:ring-primary-200"
            />
            <label :for="`c-${c}`" class="text-ink-700">{{ t(`criteria.${c}`) }}</label>
          </li>
        </ul>
        <button
          type="button"
          data-testid="region-apply"
          class="mt-3 w-full h-9 rounded-md border border-primary-200 bg-primary-50 text-primary-800 text-sm font-medium hover:bg-primary-100 transition"
          @click="apply"
        >
          {{ t('labeling.applyCriteria') }}
        </button>
      </section>

      <section>
        <div class="grid grid-cols-4 gap-2">
          <button
            v-for="a in ACTIONS"
            :key="a.id"
            type="button"
            :data-testid="a.tid"
            class="h-14 flex flex-col items-center justify-center gap-1 rounded-md border text-xs transition"
            :class="a.id === 'delete' ? 'border-red-200 text-red-600 hover:bg-red-50' : 'border-border-default text-ink-600 hover:bg-ink-50'"
            @click="onAction(a.id)"
          >
            <span class="text-base leading-none">{{ a.icon }}</span>
            {{ t(a.labelKey) }}
          </button>
        </div>
      </section>
    </div>
  </aside>
</template>
