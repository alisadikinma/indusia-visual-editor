<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useEvalStore } from '@/stores/eval'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const evalStore = useEvalStore()

const projectId = computed(() => String(route.params.id ?? ''))
const runId = computed(() => String(route.params.runId ?? ''))

const starting = ref(false)

const testSetOptions = [
  { id: 'holdout', count: 142, source: 'training-split' },
  { id: 'production_run', count: 24, source: 'last-24h-edge' },
  { id: 'upload', count: 0, source: null },
] as const

async function startEval() {
  starting.value = true
  // The MSW handler short-circuits the load; real backend would kick off the eval job.
  await evalStore.load(runId.value)
  await router.push({
    name: 'eval',
    params: { id: projectId.value, runId: runId.value },
  })
}

function backToTraining() {
  router.push({
    name: 'training',
    params: { id: projectId.value, runId: runId.value },
  })
}
</script>

<template>
  <div class="p-8 max-w-[1100px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('setupEval.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('setupEval.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('setupEval.subhead') }}</p>
    </header>

    <div
      class="rounded-xl bg-primary-50 border border-primary-200 px-5 py-4 flex items-start gap-3"
    >
      <span
        class="h-6 w-6 rounded-full bg-primary-700 text-white grid place-items-center text-xs shrink-0"
      >
        ⏸
      </span>
      <div>
        <p class="text-sm font-semibold text-primary-900">{{ t('setupEval.hitlTitle') }}</p>
        <p class="text-sm text-primary-900/80">{{ t('setupEval.hitlBlurb') }}</p>
      </div>
    </div>

    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
      <h2 class="text-base font-semibold text-ink-900">{{ t('setupEval.testSetTitle') }}</h2>
      <div class="mt-3 space-y-2">
        <label
          v-for="opt in testSetOptions"
          :key="opt.id"
          class="flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition"
          :class="
            evalStore.testSet === opt.id
              ? 'border-primary-300 bg-primary-50'
              : 'border-ink-200 hover:bg-ink-50'
          "
        >
          <input
            v-model="evalStore.testSet"
            type="radio"
            :value="opt.id"
            class="mt-1"
          />
          <div class="flex-1">
            <p class="text-sm font-medium text-ink-900">
              {{ t(`setupEval.option.${opt.id}.title`) }}
            </p>
            <p class="text-xs text-ink-500">
              {{ t(`setupEval.option.${opt.id}.blurb`) }}
            </p>
          </div>
          <span class="text-xs font-mono text-ink-500 tabular-nums">
            {{ opt.count > 0 ? `${opt.count} img` : '—' }}
          </span>
        </label>
      </div>
    </section>

    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
      <h2 class="text-base font-semibold text-ink-900">{{ t('setupEval.thresholdTitle') }}</h2>
      <ul class="mt-3 space-y-2 text-sm">
        <li class="flex items-center justify-between border-b border-ink-100 pb-2">
          <span class="text-ink-700">mAP ≥ 0.80</span>
          <span class="text-success font-mono">✓ {{ t('setupEval.estimatedPass') }}</span>
        </li>
        <li class="flex items-center justify-between border-b border-ink-100 pb-2">
          <span class="text-ink-700">F1 macro ≥ 0.80</span>
          <span class="text-success font-mono">✓ {{ t('setupEval.estimatedPass') }}</span>
        </li>
        <li class="flex items-center justify-between border-b border-ink-100 pb-2">
          <span class="text-ink-700">Per-component F1 ≥ 0.70</span>
          <span class="text-warning font-mono">~ {{ t('setupEval.atRiskFor', { n: 1 }) }}</span>
        </li>
        <li class="flex items-center justify-between">
          <span class="text-ink-700">{{ t('setupEval.coverage') }}</span>
          <span class="text-success font-mono">✓ 100%</span>
        </li>
      </ul>
    </section>

    <section class="rounded-xl bg-ink-50 border border-ink-200 p-5 flex items-start gap-4">
      <span class="text-xs font-mono text-ink-500">{{ t('setupEval.duration') }}</span>
      <span class="text-sm font-medium text-ink-900">~2 min</span>
    </section>

    <footer class="flex items-center justify-between">
      <AppButton variant="ghost" @click="backToTraining">
        ← {{ t('setupEval.backToTraining') }}
      </AppButton>
      <AppButton :disabled="starting" @click="startEval">
        {{ starting ? t('common.loading') : t('setupEval.startEval') }} →
      </AppButton>
    </footer>
  </div>
</template>
