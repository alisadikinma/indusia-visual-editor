<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useTrainingStore } from '@/stores/training'
import { useEngineerStore } from '@/stores/engineer'
import { getRegistrationPreflight, type RegistrationPreflight, type QcVerdict } from '@/api/assets'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const training = useTrainingStore()
const engineer = useEngineerStore()

const projectId = computed(() => String(route.params.id ?? ''))
const registration = ref<RegistrationPreflight | null>(null)

onMounted(async () => {
  if (!projectId.value) return
  await training.loadGate1(projectId.value, 'top')
  try {
    registration.value = await getRegistrationPreflight(projectId.value, 'top')
  } catch {
    registration.value = null // no golden uploaded for this side yet
  }
})

const regTone: Record<QcVerdict, string> = {
  ok: 'bg-primary-50 border-primary-200 text-primary-900',
  warn: 'bg-amber-50 border-amber-200 text-amber-900',
  fail: 'bg-red-50 border-red-200 text-red-900',
}

const stats = computed(() => training.datasetStats)
const perDesignator = computed(() => stats.value?.per_designator ?? [])
const componentCount = computed(() => perDesignator.value.length)
const maxCount = computed(() => Math.max(1, ...perDesignator.value.map((p) => p.count)))

const bucketMeta: Record<'sufficient' | 'moderate' | 'at_risk', { badge: string; bar: string; key: string }> = {
  sufficient: { badge: 'bg-primary-50 text-primary-700', bar: 'bg-primary-500', key: 'gate1.bucketSufficient' },
  moderate: { badge: 'bg-amber-50 text-amber-700', bar: 'bg-amber-400', key: 'gate1.bucketModerate' },
  at_risk: { badge: 'bg-red-50 text-red-700', bar: 'bg-red-500', key: 'gate1.bucketAtRisk' },
}

// Considerations are derived from the real per-component buckets + coverage
// ratio — no fabricated GPU/time numbers.
const considerations = computed(() => {
  const out: { tone: 'danger' | 'warning' | 'info' | 'ok'; text: string }[] = []
  if (!stats.value) return out
  for (const r of perDesignator.value.filter((p) => p.bucket === 'at_risk')) {
    out.push({ tone: 'danger', text: t('gate1.considAtRisk', { d: r.designator, n: r.count }) })
  }
  const moderate = perDesignator.value.filter((p) => p.bucket === 'moderate')
  if (moderate.length) {
    out.push({
      tone: 'warning',
      text: t('gate1.considModerate', { list: moderate.map((m) => m.designator).join(', ') }),
    })
  }
  out.push({
    tone: 'info',
    text: t('gate1.considCoverage', { pct: Math.round((stats.value.coverage_ratio ?? 0) * 100) }),
  })
  if (!out.some((c) => c.tone === 'danger' || c.tone === 'warning')) {
    out.unshift({ tone: 'ok', text: t('gate1.considAllGood') })
  }
  return out
})

const considToneClass: Record<string, string> = {
  danger: 'text-red-800',
  warning: 'text-amber-800',
  info: 'text-amber-900/70',
  ok: 'text-primary-800',
}

async function approveAndStart() {
  const run = await training.start(projectId.value)
  if (run) {
    await router.push({ name: 'training', params: { id: projectId.value, runId: run.id } })
  }
}
function backToLabeling() {
  router.push({ name: 'labeling', params: { id: projectId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <!-- HITL banner -->
    <div
      data-testid="gate1-hitl"
      class="flex items-start justify-between gap-4 rounded-xl bg-primary-50 border-2 border-primary-300 px-5 py-4"
    >
      <div class="flex items-start gap-3">
        <span class="h-7 w-7 grid place-items-center rounded-full bg-primary-600 text-white text-sm shrink-0">✓</span>
        <div>
          <p class="text-sm font-semibold text-primary-900">{{ t('gate1.hitlTitle') }}</p>
          <p class="text-sm text-primary-900/80">{{ t('gate1.hitlBlurb') }}</p>
        </div>
      </div>
      <button
        type="button"
        data-testid="gate1-tech-toggle"
        class="inline-flex items-center gap-2 h-8 px-3 rounded-full border text-xs font-mono shrink-0 transition"
        :class="engineer.enabled ? 'border-engineer-300 bg-engineer-50 text-engineer-800' : 'border-border-default bg-white text-ink-500 hover:text-ink-700'"
        :aria-pressed="engineer.enabled"
        @click="engineer.toggle()"
      >
        <span class="opacity-80">&lt;/&gt;</span>
        {{ t('gate1.techDetails') }}
        <span class="ml-1 inline-flex h-4 w-7 rounded-full p-0.5 transition" :class="engineer.enabled ? 'bg-engineer-600' : 'bg-ink-300'">
          <span class="h-3 w-3 rounded-full bg-white transition-transform" :class="engineer.enabled ? 'translate-x-3' : ''" />
        </span>
      </button>
    </div>

    <div v-if="training.error" class="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      {{ training.error }}
    </div>

    <!-- Registration pre-flight (T7 / G2) — relative, pixel-domain check -->
    <div
      v-if="registration"
      data-testid="gate1-registration"
      class="rounded-xl border px-5 py-4"
      :class="regTone[registration.verdict]"
    >
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-sm font-semibold">
            {{ t('gate1.registration.title') }} · {{ t(`gate1.registration.${registration.verdict}`) }}
          </p>
          <p class="text-sm opacity-80">
            {{ t('gate1.registration.blurb', {
              kp: registration.per_image[0]?.keypoints ?? 0,
              n: registration.sample_count,
            }) }}
            <template v-if="registration.pairwise_residual_px !== null">
              · {{ t('gate1.registration.residual', { px: registration.pairwise_residual_px }) }}
            </template>
          </p>
          <p
            v-if="registration.reasons.length"
            class="mt-1 text-xs opacity-70"
          >
            {{ registration.reasons.map((r) => t(`gate1.registration.reason.${r}`)).join(' · ') }}
          </p>
        </div>
        <span class="text-[11px] font-mono opacity-60 shrink-0">{{ t('gate1.registration.relativeNote') }}</span>
      </div>
    </div>

    <!-- Readiness + considerations -->
    <div class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start">
      <section class="rounded-xl bg-white border border-border-default shadow-card p-6 space-y-5">
        <div>
          <h2 class="text-lg font-semibold text-ink-900">{{ t('gate1.datasetTitle') }}</h2>
          <p class="mt-1 text-sm text-ink-500">
            {{ t('gate1.readinessLine', { total: stats?.total_regions ?? 0, n: componentCount }) }}
          </p>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div data-testid="gate1-stat-annotations" class="rounded-lg bg-surface-raised border border-border-subtle p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('gate1.statAnnotations') }}</p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-ink-900">{{ stats?.total_regions ?? 0 }}</p>
            <p class="text-[11px] text-ink-400">{{ t('gate1.annotationsAcross', { n: componentCount }) }}</p>
          </div>
          <div class="rounded-lg bg-surface-raised border border-border-subtle p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('gate1.statComponents') }}</p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-ink-900">{{ componentCount }}</p>
            <p class="text-[11px] text-ink-400">{{ t('gate1.componentsSub') }}</p>
          </div>
          <div class="rounded-lg bg-surface-raised border border-border-subtle p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('gate1.statCoverage') }}</p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-ink-900">
              {{ Math.round((stats?.coverage_ratio ?? 0) * 100) }}%
            </p>
            <p class="text-[11px] text-ink-400">{{ t('gate1.coverageSub') }}</p>
          </div>
          <div class="rounded-lg bg-surface-raised border border-border-subtle p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('gate1.statSides') }}</p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-ink-900">
              {{ stats?.side_breakdown.top ?? 0 }} / {{ stats?.side_breakdown.bottom ?? 0 }}
            </p>
            <p class="text-[11px] text-ink-400">{{ t('gate1.sidesSub') }}</p>
          </div>
        </div>

        <div data-testid="gate1-coverage">
          <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500 mb-2">{{ t('gate1.coverageTitle') }}</p>
          <ul class="space-y-2">
            <li v-for="row in perDesignator" :key="row.designator" class="flex items-center gap-3">
              <span class="w-16 text-sm font-mono text-ink-900 truncate">{{ row.designator }}</span>
              <span class="w-14 text-right text-xs font-mono tabular-nums text-ink-500">
                {{ t('gate1.exampleCount', { n: row.count }) }}
              </span>
              <span class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium" :class="bucketMeta[row.bucket].badge">
                {{ t(bucketMeta[row.bucket].key) }}
              </span>
              <span class="flex-1 h-2 rounded-full bg-ink-100 overflow-hidden">
                <span class="block h-full rounded-full" :class="bucketMeta[row.bucket].bar" :style="{ width: Math.max(6, Math.round((row.count / maxCount) * 100)) + '%' }" />
              </span>
            </li>
          </ul>
        </div>
      </section>

      <!-- Things to consider -->
      <aside data-testid="gate1-considerations" class="rounded-xl bg-amber-50 border border-amber-200 p-5 space-y-4">
        <p class="flex items-center gap-1.5 text-sm font-semibold text-amber-900">
          <span>⚠</span> {{ t('gate1.considerationsTitle') }}
        </p>
        <ul class="space-y-3">
          <li v-for="(c, i) in considerations" :key="i" class="text-[13px] leading-snug" :class="considToneClass[c.tone]">
            {{ c.text }}
          </li>
        </ul>
      </aside>
    </div>

    <!-- Engineer hyperparameters -->
    <section
      v-if="engineer.enabled"
      data-testid="gate1-hyperparams"
      class="rounded-xl bg-engineer-50 border border-engineer-200 p-5"
    >
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span class="inline-flex items-center h-5 px-2 rounded-full bg-engineer-700 text-white text-[10px] font-mono uppercase tracking-wider">ENGINEER</span>
          <h3 class="text-base font-semibold text-engineer-900">{{ t('gate1.hyperparamsTitle') }}</h3>
        </div>
        <p class="text-[11px] font-mono text-engineer-700">
          {{ training.hyperparams?.hyperparameters.grounding_source ?? '—' }}
        </p>
      </div>
      <dl class="grid grid-cols-2 md:grid-cols-5 gap-x-4 gap-y-3 text-sm font-mono">
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Epochs</dt>
          <dd class="text-engineer-900 tabular-nums">{{ training.hyperparams?.hyperparameters.epochs ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Batch</dt>
          <dd class="text-engineer-900 tabular-nums">{{ training.hyperparams?.hyperparameters.batch_size ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">LR</dt>
          <dd class="text-engineer-900 tabular-nums">{{ training.hyperparams?.hyperparameters.learning_rate ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Aug.</dt>
          <dd class="text-engineer-900">{{ training.hyperparams?.hyperparameters.augmentation_intensity ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Patience</dt>
          <dd class="text-engineer-900 tabular-nums">{{ training.hyperparams?.hyperparameters.early_stopping_patience ?? '—' }}</dd>
        </div>
      </dl>
    </section>

    <!-- Training mode -->
    <section class="rounded-xl bg-white border border-border-default shadow-card p-6">
      <h3 class="text-base font-semibold text-ink-900">{{ t('gate1.modeTitle') }}</h3>
      <p class="text-sm text-ink-500">{{ t('gate1.modeSub') }}</p>
      <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label
          data-testid="gate1-mode-scratch"
          class="flex items-start gap-3 rounded-xl border-2 p-4 cursor-pointer transition"
          :class="training.trainMode === 'scratch' ? 'border-primary-400 bg-primary-50' : 'border-border-default hover:bg-ink-50'"
        >
          <input v-model="training.trainMode" type="radio" value="scratch" class="mt-1 accent-primary-600" />
          <div class="flex-1">
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm font-medium text-ink-900">{{ t('gate1.modeScratch') }}</p>
              <span class="inline-flex items-center h-5 px-2 rounded-full bg-primary-600 text-white text-[10px] font-mono uppercase tracking-wide">
                {{ t('gate1.selected') }}
              </span>
            </div>
            <p class="mt-1 text-xs text-ink-500">{{ t('gate1.modeScratchSub') }}</p>
          </div>
        </label>
        <label
          data-testid="gate1-mode-continue"
          class="flex items-start gap-3 rounded-xl border-2 border-border-default p-4 cursor-not-allowed opacity-60"
          :title="t('gate1.modeContinueTooltip')"
        >
          <input type="radio" value="continue" class="mt-1" disabled />
          <div class="flex-1">
            <div class="flex items-center justify-between gap-2">
              <p class="text-sm font-medium text-ink-500">{{ t('gate1.modeContinue') }}</p>
              <span class="inline-flex items-center h-5 px-2 rounded-full bg-ink-200 text-ink-500 text-[10px] font-mono uppercase tracking-wide">
                {{ t('gate1.disabled') }}
              </span>
            </div>
            <p class="mt-1 text-xs text-ink-400">{{ t('gate1.modeContinueTooltip') }}</p>
          </div>
        </label>
      </div>
    </section>

    <!-- Ready footer -->
    <section class="flex items-center justify-between gap-4 rounded-xl bg-white border border-border-default shadow-card px-6 py-4">
      <div class="min-w-0">
        <p class="text-sm font-semibold text-ink-900">{{ t('gate1.readyTitle') }}</p>
        <p class="text-xs text-ink-500">{{ t('gate1.readyBlurb') }}</p>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <AppButton data-testid="gate1-back" variant="secondary" @click="backToLabeling">
          ← {{ t('gate1.backToLabeling') }}
        </AppButton>
        <AppButton data-testid="gate1-approve" :disabled="training.starting || training.loading" @click="approveAndStart">
          {{ training.starting ? t('common.loading') : t('gate1.approveAndStart') }} →
        </AppButton>
      </div>
    </section>
  </div>
</template>
