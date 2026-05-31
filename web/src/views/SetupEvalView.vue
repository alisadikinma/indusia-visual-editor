<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useEvalStore } from '@/stores/eval'
import { useTrainingStore } from '@/stores/training'
import { useToastStore } from '@/stores/toast'
import { EVAL_THRESHOLDS } from '@/api/eval'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const evalStore = useEvalStore()
const training = useTrainingStore()
const toast = useToastStore()

const projectId = computed(() => String(route.params.id ?? ''))
const runId = computed(() => String(route.params.runId ?? ''))
const starting = ref(false)

onMounted(async () => {
  if (runId.value) await training.loadRun(projectId.value, runId.value)
  // Locked test-set status (G5 / S5). Safe when absent — data stays null.
  if (projectId.value) await evalStore.fetchSplitStatus(projectId.value)
})

const totalTestCount = computed(() =>
  (evalStore.splitStatus?.perComponent ?? []).reduce((sum, c) => sum + c.testCount, 0),
)

const unstableItems = computed(() =>
  evalStore.unstableComponents.flatMap((c) =>
    c.unstableClasses.map((u) => ({ component: c.component, cls: u.class, count: u.count })),
  ),
)

// Training-run metrics (real, from the succeeded run). Surfaced as a reference
// for the readiness gates — clearly labelled "train", never as an eval result.
const trainMetrics = computed(() => {
  const m = training.currentRun?.metrics_json ?? null
  const num = (...keys: string[]): number | null => {
    if (!m) return null
    for (const k of keys) {
      const v = m[k]
      if (typeof v === 'number') return v
    }
    return null
  }
  return {
    map: num('map', 'mAP'),
    f1_macro: num('f1_macro', 'f1Macro', 'f1'),
    epochs: num('epochs', 'total_epochs'),
  }
})

const modelStatus = computed(() => training.currentRun?.status ?? 'pending')

function fmt(v: number | null): string {
  return v == null ? t('setupEval.pending') : v.toFixed(3)
}

const gates = computed(() => [
  { key: 'map', label: 'mAP', threshold: EVAL_THRESHOLDS.map_min, value: trainMetrics.value.map },
  { key: 'f1', label: 'F1 macro', threshold: EVAL_THRESHOLDS.f1_macro_min, value: trainMetrics.value.f1_macro },
  { key: 'perc', label: t('setupEval.perComponentGate'), threshold: EVAL_THRESHOLDS.per_component_f1_min, value: null },
])

const testSetOptions = ['holdout', 'production_run', 'upload'] as const

async function startEval() {
  starting.value = true
  try {
    await evalStore.load(runId.value)
    // load() swallows transport errors into evalStore.error — don't navigate
    // to the eval screen if scoring never started.
    if (evalStore.error) {
      toast.error(t('setupEval.startError'), evalStore.error)
      return
    }
    await router.push({ name: 'eval', params: { id: projectId.value, runId: runId.value } })
  } catch (err) {
    toast.error(t('setupEval.startError'), err instanceof Error ? err.message : undefined)
  } finally {
    starting.value = false
  }
}
function backToTraining() {
  router.push({ name: 'training', params: { id: projectId.value, runId: runId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <header class="space-y-1">
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('setupEval.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('setupEval.subhead') }}</p>
    </header>

    <!-- HITL banner -->
    <div data-testid="setupeval-hitl" class="flex items-start gap-3 rounded-xl bg-blue-50 border border-blue-200 px-5 py-4">
      <span class="h-7 w-7 grid place-items-center rounded-full bg-blue-500 text-white text-sm shrink-0">i</span>
      <div>
        <p class="text-sm font-semibold text-blue-900">{{ t('setupEval.hitlTitle') }}</p>
        <p class="text-sm text-blue-900/80">{{ t('setupEval.hitlBlurb') }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start">
      <div class="space-y-6">
        <!-- Model under evaluation -->
        <section data-testid="setupeval-model" class="rounded-xl bg-white border border-border-default shadow-card p-6">
          <h2 class="text-base font-semibold text-ink-900">{{ t('setupEval.modelTitle') }}</h2>
          <p class="text-sm text-ink-500 mb-4">{{ t('setupEval.modelSub') }}</p>
          <dl class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('setupEval.run') }}</dt>
              <dd class="font-mono text-ink-900">#{{ runId.slice(0, 8) }}</dd>
            </div>
            <div>
              <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('setupEval.epochs') }}</dt>
              <dd class="font-mono tabular-nums text-ink-900">{{ trainMetrics.epochs ?? '—' }}</dd>
            </div>
            <div>
              <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('setupEval.status') }}</dt>
              <dd class="font-medium" :class="modelStatus === 'succeeded' ? 'text-primary-700' : 'text-ink-700'">
                {{ t(`training.status.${modelStatus}`) }}
              </dd>
            </div>
            <div>
              <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">mAP ({{ t('setupEval.train') }})</dt>
              <dd class="font-mono tabular-nums text-ink-900">{{ fmt(trainMetrics.map) }}</dd>
            </div>
            <div>
              <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">F1 macro ({{ t('setupEval.train') }})</dt>
              <dd class="font-mono tabular-nums text-ink-900">{{ fmt(trainMetrics.f1_macro) }}</dd>
            </div>
          </dl>
        </section>

        <!-- Test set -->
        <section data-testid="setupeval-testset" class="rounded-xl bg-white border border-border-default shadow-card p-6">
          <h2 class="text-base font-semibold text-ink-900">{{ t('setupEval.testSetTitle') }}</h2>
          <p class="text-sm text-ink-500 mb-3">{{ t('setupEval.testSetSub') }}</p>
          <div class="space-y-2">
            <label
              v-for="opt in testSetOptions"
              :key="opt"
              class="flex items-start gap-3 rounded-xl border-2 p-4 cursor-pointer transition"
              :class="evalStore.testSet === opt ? 'border-primary-400 bg-primary-50' : 'border-border-default hover:bg-ink-50'"
            >
              <input v-model="evalStore.testSet" type="radio" :value="opt" class="mt-1 accent-primary-600" />
              <div class="flex-1">
                <p class="text-sm font-medium text-ink-900">{{ t(`setupEval.option.${opt}.title`) }}</p>
                <p class="text-xs text-ink-500">{{ t(`setupEval.option.${opt}.blurb`) }}</p>
              </div>
            </label>
          </div>

          <!-- Locked test set (S5) — only meaningful for the holdout split -->
          <div
            v-if="evalStore.testSet === 'holdout' && evalStore.splitStatus"
            data-testid="setupeval-locked-split"
            class="mt-3 rounded-xl border border-border-default bg-surface-raised p-4 space-y-3"
          >
            <div class="flex items-start gap-3">
              <span class="h-6 w-6 grid place-items-center rounded-md bg-primary-50 text-primary-700 shrink-0">
                <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="5" y="11" width="14" height="10" rx="2" />
                  <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                </svg>
              </span>
              <div class="flex-1">
                <p class="text-sm font-semibold text-ink-900">{{ t('setupEval.split.lockedTitle') }}</p>
                <p class="text-xs text-ink-500">{{ t('setupEval.split.lockedBlurb') }}</p>
              </div>
            </div>
            <div class="flex flex-wrap gap-2 text-[11px] font-mono">
              <span class="inline-flex items-center h-6 px-2 rounded-full bg-ink-100 text-ink-700">
                {{ t('setupEval.split.seedLabel') }} {{ evalStore.lockedSeed }}
              </span>
              <span class="inline-flex items-center h-6 px-2 rounded-full bg-ink-100 text-ink-700 tabular-nums">
                {{ t('setupEval.split.totalTest', { n: totalTestCount }) }}
              </span>
              <span class="inline-flex items-center h-6 px-2 rounded-full bg-ink-100 text-ink-700 tabular-nums">
                {{ t('setupEval.split.components', { n: evalStore.splitStatus.perComponent.length }) }}
              </span>
            </div>

            <div
              v-if="evalStore.belowFloor"
              data-testid="setupeval-belowfloor"
              class="rounded-lg bg-amber-50 border border-amber-200 px-3 py-2.5 space-y-1.5"
            >
              <p class="text-xs font-semibold text-amber-800">{{ t('setupEval.split.belowFloorTitle') }}</p>
              <ul class="space-y-0.5">
                <li
                  v-for="it in unstableItems"
                  :key="`${it.component}-${it.cls}`"
                  class="text-[11px] font-mono text-amber-700 tabular-nums"
                >
                  {{ t('setupEval.split.belowFloorItem', { component: it.component, cls: it.cls, count: it.count }) }}
                </li>
              </ul>
              <p class="text-[11px] text-amber-700/80">{{ t('setupEval.split.belowFloorNote') }}</p>
            </div>
          </div>
        </section>
      </div>

      <!-- Readiness -->
      <aside class="space-y-4">
        <section data-testid="setupeval-readiness" class="rounded-xl bg-white border border-border-default shadow-card p-5">
          <h2 class="text-base font-semibold text-ink-900">{{ t('setupEval.readinessTitle') }}</h2>
          <p class="text-xs text-ink-500 mb-3">{{ t('setupEval.readinessSub') }}</p>
          <ul class="space-y-2">
            <li v-for="g in gates" :key="g.key" class="flex items-center justify-between rounded-lg bg-surface-raised px-3 py-2">
              <div>
                <p class="text-sm text-ink-900">{{ g.label }}</p>
                <p class="text-[11px] font-mono text-ink-400">≥ {{ g.threshold.toFixed(2) }}</p>
              </div>
              <span
                class="inline-flex items-center h-6 px-2 rounded-full text-xs font-mono"
                :class="g.value == null ? 'bg-ink-100 text-ink-500' : g.value >= g.threshold ? 'bg-primary-50 text-primary-700' : 'bg-amber-50 text-amber-700'"
              >
                {{ g.value == null ? t('setupEval.pending') : `${g.value.toFixed(3)} (${t('setupEval.train')})` }}
              </span>
            </li>
          </ul>
        </section>

        <div class="rounded-xl bg-surface-raised border border-border-default p-4">
          <h3 class="text-sm font-semibold text-ink-900 mb-2">{{ t('setupEval.thingsTitle') }}</h3>
          <ul class="space-y-1.5 text-[13px] text-ink-600">
            <li class="flex gap-2"><span class="text-ink-400">·</span><span>{{ t('setupEval.thing1') }}</span></li>
            <li class="flex gap-2"><span class="text-ink-400">·</span><span>{{ t('setupEval.thing2') }}</span></li>
          </ul>
        </div>
      </aside>
    </div>

    <footer class="flex items-center justify-between rounded-xl bg-white border border-border-default shadow-card px-6 py-4">
      <AppButton data-testid="setupeval-back" variant="secondary" @click="backToTraining">
        ← {{ t('setupEval.backToTraining') }}
      </AppButton>
      <AppButton data-testid="setupeval-start" :disabled="starting" @click="startEval">
        {{ starting ? t('common.loading') : t('setupEval.startEval') }} →
      </AppButton>
    </footer>
  </div>
</template>
