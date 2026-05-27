<script setup lang="ts">
import { computed } from 'vue'
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

const idShort = computed<string>(() => {
  const id = props.region?.id ?? ''
  return id.length > 12 ? id.slice(0, 12) + '…' : id
})

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

const selected = computed<string[]>(() => {
  return []
})

function apply() {
  emit('applyCriteria', selected.value)
}
</script>

<template>
  <aside class="w-80 bg-white border-l border-ink-200 flex flex-col">
    <header class="px-5 py-4 border-b border-ink-200">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('labeling.regionDetailTitle') }}
      </p>
      <h3 class="mt-0.5 text-base font-semibold text-ink-900">
        {{ designator || t('labeling.noSelection') }}
      </h3>
    </header>

    <div v-if="!region" class="flex-1 grid place-items-center p-6 text-center">
      <p class="text-sm text-ink-500">{{ t('labeling.selectHint') }}</p>
    </div>

    <div v-else class="flex-1 overflow-y-auto p-5 space-y-5">
      <section>
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500 mb-2">
          {{ t('labeling.geometry') }}
        </p>
        <dl class="grid grid-cols-2 gap-x-3 gap-y-2 text-sm font-mono tabular-nums">
          <div class="flex justify-between">
            <dt class="text-ink-500">X</dt>
            <dd class="text-ink-900">{{ fmt(value.x) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-500">Y</dt>
            <dd class="text-ink-900">{{ fmt(value.y) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-500">W</dt>
            <dd class="text-ink-900">{{ fmt(value.width) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-ink-500">H</dt>
            <dd class="text-ink-900">{{ fmt(value.height) }}</dd>
          </div>
          <div class="flex justify-between col-span-2">
            <dt class="text-ink-500">R°</dt>
            <dd class="text-ink-900">{{ fmt(value.rotation) }}</dd>
          </div>
        </dl>
      </section>

      <section>
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500 mb-2">
          ID
        </p>
        <p class="text-sm font-mono text-ink-700">{{ idShort || '—' }}</p>
      </section>

      <section>
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500 mb-2">
          {{ t('labeling.criteria') }}
        </p>
        <ul class="space-y-1.5 text-sm">
          <li v-for="c in CRITERIA" :key="c" class="flex items-center gap-2">
            <input
              :id="`c-${c}`"
              type="checkbox"
              class="h-4 w-4 rounded border-ink-300 text-primary-700 focus:ring-primary-200"
            />
            <label :for="`c-${c}`" class="text-ink-700">{{ t(`criteria.${c}`) }}</label>
          </li>
        </ul>
        <button
          type="button"
          class="mt-3 w-full h-9 rounded-md border border-primary-200 bg-primary-50 text-primary-800 text-sm font-medium hover:bg-primary-100 transition"
          @click="apply"
        >
          {{ t('labeling.applyCriteria') }}
        </button>
      </section>

      <section>
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500 mb-2">
          {{ t('labeling.actions') }}
        </p>
        <div class="grid grid-cols-4 gap-2">
          <button
            type="button"
            class="h-9 grid place-items-center rounded-md border border-ink-200 hover:bg-ink-50"
            :title="t('labeling.actionRelate')"
            @click="emit('relate')"
          >
            <span class="text-sm">↔</span>
          </button>
          <button
            type="button"
            class="h-9 grid place-items-center rounded-md border border-ink-200 hover:bg-ink-50"
            :title="t('labeling.actionCopy')"
            @click="emit('copy')"
          >
            <span class="text-sm">⎘</span>
          </button>
          <button
            type="button"
            class="h-9 grid place-items-center rounded-md border border-ink-200 hover:bg-ink-50"
            :title="t('labeling.actionVisibility')"
            @click="emit('toggleVisible')"
          >
            <span class="text-sm">👁</span>
          </button>
          <button
            type="button"
            class="h-9 grid place-items-center rounded-md border border-red-200 text-red-600 hover:bg-red-50"
            :title="t('labeling.actionDelete')"
            @click="emit('delete')"
          >
            <span class="text-sm">✕</span>
          </button>
        </div>
      </section>
    </div>
  </aside>
</template>
