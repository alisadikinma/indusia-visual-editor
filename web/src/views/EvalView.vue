<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useEvalStore } from '@/stores/eval'
import { EVAL_THRESHOLDS } from '@/api/eval'
import type { EvalPrediction } from '@/api/eval'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const evalStore = useEvalStore()

const projectId = computed(() => String(route.params.id ?? ''))
const runId = computed(() => String(route.params.runId ?? ''))
const shortRun = computed(() => runId.value.slice(0, 8))

onMounted(async () => {
  if (runId.value) await evalStore.load(runId.value)
})

const verdictMeta = computed(() => {
  switch (evalStore.verdict) {
    case 'passed':
      return { tone: 'bg-primary-50 border-primary-300', icon: '✓', iconBg: 'bg-primary-600', title: 'eval.passedTitle', blurb: 'eval.passedBlurb' }
    case 'corrected':
      return { tone: 'bg-amber-50 border-amber-300', icon: '↻', iconBg: 'bg-amber-500', title: 'eval.correctedTitle', blurb: 'eval.correctedBlurb' }
    default:
      return { tone: 'bg-amber-50 border-amber-300', icon: '⚠', iconBg: 'bg-amber-500', title: 'eval.failingTitle', blurb: 'eval.failingBlurb' }
  }
})

// Concrete failing-detail line, derived from real per-component data.
const failingDetail = computed(() => {
  const c = evalStore.failingComponents[0]
  if (!c) return ''
  return t('eval.failingDetail', {
    d: c.designator,
    f1: c.f1.toFixed(2),
    threshold: EVAL_THRESHOLDS.per_component_f1_min.toFixed(2),
  })
})

function fmtPct(v: number | undefined | null): string {
  return v == null ? '—' : (v * 100).toFixed(1) + '%'
}
function tone(value: number, threshold: number): string {
  return value >= threshold ? 'text-primary-700' : 'text-amber-700'
}

const metricTiles = computed(() => {
  const m = evalStore.data?.metrics
  if (!m) return []
  return [
    { label: 'mAP@0.5', v: m.map, th: EVAL_THRESHOLDS.map_min },
    { label: 'F1 macro', v: m.f1_macro, th: EVAL_THRESHOLDS.f1_macro_min },
    { label: 'Precision', v: m.precision_macro, th: EVAL_THRESHOLDS.f1_macro_min },
    { label: 'Recall', v: m.recall_macro, th: EVAL_THRESHOLDS.f1_macro_min },
  ]
})

const filterChips = computed(() => {
  const preds = evalStore.data?.predictions ?? []
  const count = (s: EvalPrediction['status']) => preds.filter((p) => p.status === s).length
  return [
    { key: 'all' as const, labelKey: 'eval.filterAll', n: preds.length },
    { key: 'fp' as const, labelKey: 'eval.filterFp', n: count('fp') },
    { key: 'fn' as const, labelKey: 'eval.filterFn', n: count('fn') },
  ]
})

const statusBadge: Record<string, string> = {
  tp: 'bg-primary-600 text-white',
  fp: 'bg-amber-500 text-white',
  fn: 'bg-red-500 text-white',
  tn: 'bg-ink-400 text-white',
}

function openCorrection() {
  const ids = evalStore.failingComponents.map((c) => c.designator).join(',')
  router.push({
    name: 'labeling',
    params: { id: projectId.value },
    query: { correction: '1', samples: ids, run: runId.value },
  })
}
function gotoGate2() {
  router.push({ name: 'gate2', params: { id: projectId.value, runId: runId.value } })
}
function rerunTraining() {
  router.push({ name: 'gate1', params: { id: projectId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <header>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('eval.title') }}</h1>
    </header>

    <div v-if="evalStore.loading" class="text-sm font-mono text-ink-500">{{ t('common.loading') }}</div>
    <div v-if="evalStore.error" class="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      {{ evalStore.error }}
    </div>

    <template v-if="evalStore.data">
      <!-- Verdict banner -->
      <div
        data-testid="eval-banner"
        :data-verdict="evalStore.verdict"
        class="flex items-start gap-3 rounded-xl border-2 px-5 py-4"
        :class="verdictMeta.tone"
      >
        <span class="h-7 w-7 grid place-items-center rounded-full text-white text-sm shrink-0" :class="verdictMeta.iconBg">
          {{ verdictMeta.icon }}
        </span>
        <div>
          <p class="text-sm font-semibold text-ink-900">{{ t(verdictMeta.title) }}</p>
          <p class="text-sm text-ink-700">{{ failingDetail || t(verdictMeta.blurb) }}</p>
        </div>
      </div>

      <!-- Run summary + confusion -->
      <section class="rounded-xl bg-white border border-border-default shadow-card p-6 flex items-start justify-between gap-6 flex-wrap">
        <div>
          <h2 class="text-base font-semibold text-ink-900">{{ t('eval.runTitle', { id: shortRun }) }}</h2>
          <p class="text-sm text-ink-500">{{ t('eval.runSub', { n: evalStore.data.predictions.length }) }}</p>
        </div>
        <div class="flex items-center gap-6">
          <div class="text-center">
            <p class="text-2xl font-semibold font-mono tabular-nums text-amber-700">{{ evalStore.data.metrics.false_positives }}</p>
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('eval.fp') }}</p>
          </div>
          <div class="text-center">
            <p class="text-2xl font-semibold font-mono tabular-nums text-red-700">{{ evalStore.data.metrics.false_negatives }}</p>
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('eval.fn') }}</p>
          </div>
        </div>
      </section>

      <!-- Metric tiles -->
      <div data-testid="eval-metrics" class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div v-for="m in metricTiles" :key="m.label" class="rounded-xl bg-white border border-border-default shadow-card p-4">
          <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ m.label }}</p>
          <p class="mt-1 text-2xl font-semibold font-mono tabular-nums" :class="tone(m.v, m.th)">{{ m.v.toFixed(3) }}</p>
          <p class="text-[11px] font-mono text-ink-500">{{ m.v >= m.th ? '✓' : '✗' }} ≥ {{ m.th.toFixed(2) }}</p>
        </div>
      </div>

      <!-- Filter chips -->
      <div data-testid="eval-filters" class="flex items-center gap-2 flex-wrap">
        <span class="text-xs font-mono text-ink-500">{{ t('eval.filterLabel') }}</span>
        <button
          v-for="chip in filterChips"
          :key="chip.key"
          type="button"
          :data-testid="`eval-filter-${chip.key}`"
          class="h-8 px-3 rounded-full text-xs font-medium border transition"
          :class="evalStore.predictionFilter === chip.key ? 'border-amber-300 bg-amber-100 text-amber-800' : 'border-border-default bg-white text-ink-500 hover:text-ink-900'"
          @click="evalStore.setFilter(chip.key)"
        >
          {{ t(chip.labelKey) }} ({{ chip.n }})
        </button>
      </div>

      <!-- Prediction cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <article
          v-for="p in evalStore.filteredPredictions"
          :key="p.id"
          data-testid="eval-pred-card"
          class="rounded-xl border border-border-default overflow-hidden bg-white"
        >
          <div class="relative aspect-[4/3] bg-ink-900 grid place-items-center">
            <img v-if="p.thumbnail_url" :src="p.thumbnail_url" :alt="p.designator" class="h-full w-full object-cover" />
            <span v-else class="text-[10px] font-mono uppercase tracking-wider text-ink-500">{{ p.designator }}</span>
            <span class="absolute top-2 right-2 inline-flex items-center h-5 px-2 rounded-full text-[10px] font-mono uppercase" :class="statusBadge[p.status]">
              {{ p.status }}
            </span>
          </div>
          <div class="p-3">
            <p class="text-sm font-mono font-medium text-ink-900">{{ p.designator }}</p>
            <p class="text-[11px] font-mono text-ink-500">conf {{ p.confidence.toFixed(2) }}</p>
          </div>
        </article>
      </div>

      <!-- Failing components -->
      <section
        v-if="evalStore.failingComponents.length > 0"
        data-testid="eval-failing"
        class="rounded-xl bg-white border border-border-default shadow-card p-5"
      >
        <header class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold text-ink-900">{{ t('eval.failingTitle2') }}</h2>
          <span class="text-xs font-mono text-ink-500">{{ evalStore.failingComponents.length }} {{ t('eval.componentsBelowThreshold') }}</span>
        </header>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <button
            v-for="c in evalStore.failingComponents"
            :key="c.designator"
            type="button"
            class="text-left rounded-lg border border-amber-200 bg-amber-50 hover:bg-amber-100 px-4 py-3 transition"
            @click="openCorrection"
          >
            <p class="text-sm font-medium text-amber-900 font-mono">{{ c.designator }}</p>
            <p class="text-xs text-amber-700 font-mono mt-0.5">
              F1 {{ fmtPct(c.f1) }} · P {{ fmtPct(c.precision) }} · R {{ fmtPct(c.recall) }}
            </p>
          </button>
        </div>
      </section>

      <!-- Per-component table -->
      <section data-testid="eval-table" class="rounded-xl bg-white border border-border-default shadow-card p-5">
        <header class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold text-ink-900">{{ t('eval.perComponentTitle') }}</h2>
          <span class="text-xs font-mono text-ink-500">{{ evalStore.data.metrics.per_component.length }} {{ t('eval.components') }}</span>
        </header>
        <div class="rounded-lg border border-border-default overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-surface-raised text-[11px] font-mono uppercase tracking-wider text-ink-500">
              <tr>
                <th class="text-left px-4 py-2 font-medium">{{ t('training.colDesignator') }}</th>
                <th class="text-right px-4 py-2 font-medium">F1</th>
                <th class="text-right px-4 py-2 font-medium">P</th>
                <th class="text-right px-4 py-2 font-medium">R</th>
                <th class="text-right px-4 py-2 font-medium">N</th>
                <th class="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in evalStore.data.metrics.per_component" :key="c.designator" class="border-t border-border-subtle">
                <td class="px-4 py-2 font-mono">{{ c.designator }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums" :class="tone(c.f1, EVAL_THRESHOLDS.per_component_f1_min)">{{ fmtPct(c.f1) }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums">{{ fmtPct(c.precision) }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums">{{ fmtPct(c.recall) }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums text-ink-500">{{ c.support }}</td>
                <td class="px-4 py-2">
                  <span class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium" :class="c.pass ? 'bg-primary-50 text-primary-700' : 'bg-red-50 text-red-700'">
                    {{ c.pass ? t('eval.passLabel') : t('eval.failLabel') }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Footer -->
      <footer class="flex items-center justify-between rounded-xl bg-white border border-border-default shadow-card px-6 py-4">
        <AppButton variant="secondary" @click="router.push({ name: 'setup-eval', params: { id: projectId, runId } })">
          ← {{ t('eval.backToSetup') }}
        </AppButton>
        <AppButton
          v-if="evalStore.verdict === 'failing'"
          data-testid="eval-action"
          @click="openCorrection"
        >
          {{ t('eval.correctSamples', { n: evalStore.wrongCount }) }}
        </AppButton>
        <AppButton
          v-else-if="evalStore.verdict === 'corrected'"
          data-testid="eval-action"
          @click="rerunTraining"
        >
          {{ t('eval.setupRetrain') }} →
        </AppButton>
        <AppButton v-else data-testid="eval-action" @click="gotoGate2">
          {{ t('eval.promote') }} →
        </AppButton>
      </footer>
    </template>
  </div>
</template>
