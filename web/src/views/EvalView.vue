<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useEvalStore } from '@/stores/eval'
import { EVAL_THRESHOLDS } from '@/api/eval'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const evalStore = useEvalStore()

const projectId = computed(() => String(route.params.id ?? ''))
const runId = computed(() => String(route.params.runId ?? ''))

onMounted(async () => {
  if (!runId.value) return
  await evalStore.load(runId.value)
})

const verdictBanner = computed(() => {
  switch (evalStore.verdict) {
    case 'failing':
      return {
        tone: 'bg-red-50 border-red-200 text-red-900',
        accent: 'text-red-700',
        titleKey: 'eval.failingTitle',
        blurbKey: 'eval.failingBlurb',
      }
    case 'corrected':
      return {
        tone: 'bg-amber-50 border-amber-200 text-amber-900',
        accent: 'text-amber-700',
        titleKey: 'eval.correctedTitle',
        blurbKey: 'eval.correctedBlurb',
      }
    case 'passed':
      return {
        tone: 'bg-primary-50 border-primary-200 text-primary-900',
        accent: 'text-primary-700',
        titleKey: 'eval.passedTitle',
        blurbKey: 'eval.passedBlurb',
      }
    default:
      return {
        tone: 'bg-ink-100 border-ink-200 text-ink-700',
        accent: 'text-ink-500',
        titleKey: 'eval.unknownTitle',
        blurbKey: 'eval.unknownBlurb',
      }
  }
})

function fmtPct(v: number | undefined | null): string {
  if (v == null) return '—'
  return (v * 100).toFixed(1) + '%'
}

function metricTone(value: number, threshold: number): string {
  return value >= threshold ? 'text-success' : 'text-danger'
}

function openCorrection() {
  const failingIds = evalStore.failingComponents.map((c) => c.designator).join(',')
  router.push({
    name: 'labeling',
    params: { id: projectId.value },
    query: { correction: '1', samples: failingIds },
  })
}

function gotoGate2() {
  router.push({
    name: 'gate2',
    params: { id: projectId.value, runId: runId.value },
  })
}

function rerunTraining() {
  router.push({ name: 'gate1', params: { id: projectId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('eval.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('eval.title') }}</h1>
    </header>

    <div
      v-if="evalStore.data"
      class="rounded-xl border px-5 py-4 flex items-start gap-3"
      :class="verdictBanner.tone"
    >
      <span
        class="h-6 w-6 rounded-full grid place-items-center text-xs font-mono shrink-0"
        :class="verdictBanner.accent"
      >
        {{ evalStore.verdict === 'passed' ? '✓' : evalStore.verdict === 'corrected' ? '↻' : '✕' }}
      </span>
      <div class="flex-1">
        <p class="text-sm font-semibold">{{ t(verdictBanner.titleKey) }}</p>
        <p class="text-sm opacity-90">{{ t(verdictBanner.blurbKey) }}</p>
      </div>
    </div>

    <div v-if="evalStore.loading" class="text-sm font-mono text-ink-500">
      {{ t('common.loading') }}
    </div>
    <div
      v-if="evalStore.error"
      class="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
    >
      {{ evalStore.error }}
    </div>

    <div v-if="evalStore.data" class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">mAP</p>
        <p
          class="mt-1 text-2xl font-semibold font-mono tabular-nums"
          :class="metricTone(evalStore.data.metrics.map, EVAL_THRESHOLDS.map_min)"
        >
          {{ fmtPct(evalStore.data.metrics.map) }}
        </p>
        <p class="text-[11px] font-mono text-ink-500">≥ {{ fmtPct(EVAL_THRESHOLDS.map_min) }}</p>
      </div>
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">F1 macro</p>
        <p
          class="mt-1 text-2xl font-semibold font-mono tabular-nums"
          :class="metricTone(evalStore.data.metrics.f1_macro, EVAL_THRESHOLDS.f1_macro_min)"
        >
          {{ fmtPct(evalStore.data.metrics.f1_macro) }}
        </p>
        <p class="text-[11px] font-mono text-ink-500">≥ {{ fmtPct(EVAL_THRESHOLDS.f1_macro_min) }}</p>
      </div>
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">FP</p>
        <p class="mt-1 text-2xl font-semibold font-mono tabular-nums text-danger">
          {{ evalStore.data.metrics.false_positives }}
        </p>
      </div>
      <div class="rounded-xl bg-white border border-ink-200 shadow-card p-4">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">FN</p>
        <p class="mt-1 text-2xl font-semibold font-mono tabular-nums text-warning">
          {{ evalStore.data.metrics.false_negatives }}
        </p>
      </div>
    </div>

    <section
      v-if="evalStore.data && evalStore.failingComponents.length > 0"
      class="rounded-xl bg-white border border-ink-200 shadow-card p-5"
    >
      <header class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold text-ink-900">{{ t('eval.failingTitle2') }}</h2>
        <span class="text-xs font-mono text-ink-500">
          {{ evalStore.failingComponents.length }} {{ t('eval.componentsBelowThreshold') }}
        </span>
      </header>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <button
          v-for="c in evalStore.failingComponents"
          :key="c.designator"
          type="button"
          class="text-left rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 px-4 py-3 transition"
          @click="openCorrection"
        >
          <p class="text-sm font-medium text-red-900 font-mono">{{ c.designator }}</p>
          <p class="text-xs text-red-700 font-mono mt-0.5">
            F1 {{ fmtPct(c.f1) }} · P {{ fmtPct(c.precision) }} · R {{ fmtPct(c.recall) }}
          </p>
        </button>
      </div>
    </section>

    <section
      v-if="evalStore.data"
      class="rounded-xl bg-white border border-ink-200 shadow-card p-5"
    >
      <header class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold text-ink-900">
          {{ t('eval.perComponentTitle') }}
        </h2>
        <span class="text-xs font-mono text-ink-500">
          {{ evalStore.data.metrics.per_component.length }} {{ t('eval.components') }}
        </span>
      </header>
      <div class="rounded-lg border border-ink-200 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
            <tr>
              <th class="text-left px-4 py-2 font-medium">{{ t('training.colDesignator') }}</th>
              <th class="text-right px-4 py-2 font-medium">F1</th>
              <th class="text-right px-4 py-2 font-medium">P</th>
              <th class="text-right px-4 py-2 font-medium">R</th>
              <th class="text-right px-4 py-2 font-medium">N</th>
              <th class="text-left px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="c in evalStore.data.metrics.per_component"
              :key="c.designator"
              class="border-t border-ink-100"
            >
              <td class="px-4 py-2 font-mono">{{ c.designator }}</td>
              <td
                class="px-4 py-2 text-right font-mono tabular-nums"
                :class="metricTone(c.f1, EVAL_THRESHOLDS.per_component_f1_min)"
              >
                {{ fmtPct(c.f1) }}
              </td>
              <td class="px-4 py-2 text-right font-mono tabular-nums">{{ fmtPct(c.precision) }}</td>
              <td class="px-4 py-2 text-right font-mono tabular-nums">{{ fmtPct(c.recall) }}</td>
              <td class="px-4 py-2 text-right font-mono tabular-nums text-ink-500">
                {{ c.support }}
              </td>
              <td class="px-4 py-2">
                <span
                  class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                  :class="c.pass ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'"
                >
                  {{ c.pass ? t('eval.passLabel') : t('eval.failLabel') }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <footer class="flex items-center justify-between">
      <AppButton
        variant="ghost"
        @click="router.push({ name: 'setup-eval', params: { id: projectId, runId } })"
      >
        ← {{ t('eval.backToSetup') }}
      </AppButton>
      <div class="flex items-center gap-3">
        <AppButton
          v-if="evalStore.verdict === 'failing'"
          variant="primary"
          @click="openCorrection"
        >
          {{ t('eval.correctSamples', { n: evalStore.wrongCount }) }}
        </AppButton>
        <AppButton
          v-else-if="evalStore.verdict === 'corrected'"
          variant="primary"
          @click="rerunTraining"
        >
          {{ t('eval.setupRetrain') }} →
        </AppButton>
        <AppButton v-else variant="primary" @click="gotoGate2">
          {{ t('eval.promote') }} →
        </AppButton>
      </div>
    </footer>
  </div>
</template>
