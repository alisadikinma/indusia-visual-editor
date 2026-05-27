<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useTrainingStore } from '@/stores/training'
import { useEngineerStore } from '@/stores/engineer'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const training = useTrainingStore()
const engineer = useEngineerStore()

const projectId = computed(() => String(route.params.id ?? ''))

onMounted(async () => {
  if (!projectId.value) return
  await training.loadGate1(projectId.value, 'top')
})

const buckets = computed(() => {
  const stats = training.datasetStats
  if (!stats) return { sufficient: 0, moderate: 0, at_risk: 0 }
  return stats.per_designator.reduce(
    (acc, item) => {
      acc[item.bucket]++
      return acc
    },
    { sufficient: 0, moderate: 0, at_risk: 0 } as Record<string, number>,
  )
})

function bucketKey(b: 'sufficient' | 'moderate' | 'at_risk'): string {
  return b === 'at_risk' ? 'gate1.bucketAtRisk' : `gate1.bucket${b.charAt(0).toUpperCase()}${b.slice(1)}`
}

async function approveAndStart() {
  const run = await training.start(projectId.value)
  if (run) {
    await router.push({
      name: 'training',
      params: { id: projectId.value, runId: run.id },
    })
  }
}

function backToLabeling() {
  router.push({ name: 'labeling', params: { id: projectId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('gate1.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('gate1.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('gate1.subhead') }}</p>
    </header>

    <div
      class="rounded-xl bg-primary-50 border border-primary-200 px-5 py-4 flex items-start gap-3"
    >
      <span class="h-6 w-6 rounded-full bg-primary-700 text-white grid place-items-center text-xs shrink-0">
        ⏸
      </span>
      <div>
        <p class="text-sm font-semibold text-primary-900">{{ t('gate1.hitlTitle') }}</p>
        <p class="text-sm text-primary-900/80">{{ t('gate1.hitlBlurb') }}</p>
      </div>
    </div>

    <div
      v-if="training.error"
      class="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700"
    >
      {{ training.error }}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <section
        class="lg:col-span-2 rounded-xl bg-white border border-ink-200 shadow-card p-5 space-y-4"
      >
        <header class="flex items-center justify-between">
          <h2 class="text-base font-semibold text-ink-900">{{ t('gate1.datasetTitle') }}</h2>
          <span class="text-xs font-mono text-ink-500">
            {{ training.datasetStats?.total_regions ?? 0 }} {{ t('gate1.regions') }}
          </span>
        </header>

        <div class="grid grid-cols-3 gap-3">
          <div class="rounded-lg bg-success/5 border border-success/30 p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-success">
              {{ t('gate1.bucketSufficient') }}
            </p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-success">
              {{ buckets.sufficient }}
            </p>
          </div>
          <div class="rounded-lg bg-warning/5 border border-warning/30 p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-warning">
              {{ t('gate1.bucketModerate') }}
            </p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-warning">
              {{ buckets.moderate }}
            </p>
          </div>
          <div class="rounded-lg bg-danger/5 border border-danger/30 p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-danger">
              {{ t('gate1.bucketAtRisk') }}
            </p>
            <p class="mt-0.5 text-2xl font-semibold font-mono tabular-nums text-danger">
              {{ buckets.at_risk }}
            </p>
          </div>
        </div>

        <div class="rounded-lg border border-ink-200 overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
              <tr>
                <th class="text-left px-4 py-2 font-medium">{{ t('gate1.colDesignator') }}</th>
                <th class="text-right px-4 py-2 font-medium">{{ t('gate1.colCount') }}</th>
                <th class="text-left px-4 py-2 font-medium">{{ t('gate1.colBucket') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in training.datasetStats?.per_designator ?? []"
                :key="row.designator"
                class="border-t border-ink-100"
              >
                <td class="px-4 py-2 font-mono">{{ row.designator }}</td>
                <td class="px-4 py-2 text-right font-mono tabular-nums">{{ row.count }}</td>
                <td class="px-4 py-2">
                  <span
                    class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                    :class="
                      row.bucket === 'sufficient'
                        ? 'bg-success/10 text-success'
                        : row.bucket === 'moderate'
                          ? 'bg-warning/10 text-warning'
                          : 'bg-danger/10 text-danger'
                    "
                  >
                    {{ t(bucketKey(row.bucket)) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="space-y-4">
        <div class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
          <h3 class="text-base font-semibold text-ink-900">{{ t('gate1.modeTitle') }}</h3>
          <div class="mt-3 space-y-2">
            <label
              class="flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition"
              :class="
                training.trainMode === 'scratch'
                  ? 'border-primary-300 bg-primary-50'
                  : 'border-ink-200 hover:bg-ink-50'
              "
            >
              <input v-model="training.trainMode" type="radio" value="scratch" class="mt-1" />
              <div>
                <p class="text-sm font-medium text-ink-900">{{ t('gate1.modeScratch') }}</p>
                <p class="text-xs text-ink-500">{{ t('gate1.modeScratchBlurb') }}</p>
              </div>
            </label>
            <label
              class="flex items-start gap-3 rounded-lg border p-3 cursor-not-allowed opacity-60 border-ink-200"
              :title="t('gate1.modeContinueTooltip')"
            >
              <input type="radio" value="continue" class="mt-1" disabled />
              <div>
                <p class="text-sm font-medium text-ink-500">{{ t('gate1.modeContinue') }}</p>
                <p class="text-xs text-ink-400">{{ t('gate1.modeContinueTooltip') }}</p>
              </div>
            </label>
          </div>
        </div>

        <div class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
          <h3 class="text-base font-semibold text-ink-900">{{ t('gate1.considerationsTitle') }}</h3>
          <ul class="mt-3 space-y-2 text-sm text-ink-600">
            <li class="flex gap-2">
              <span class="text-primary-700 mt-0.5">·</span>
              <span>{{ t('gate1.consid1') }}</span>
            </li>
            <li class="flex gap-2">
              <span class="text-primary-700 mt-0.5">·</span>
              <span>{{ t('gate1.consid2') }}</span>
            </li>
            <li class="flex gap-2">
              <span class="text-primary-700 mt-0.5">·</span>
              <span>{{ t('gate1.consid3') }}</span>
            </li>
          </ul>
        </div>
      </section>
    </div>

    <section
      v-if="engineer.enabled"
      class="rounded-xl bg-engineer-50 border border-engineer-200 p-5"
    >
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2">
          <span
            class="inline-flex items-center h-5 px-2 rounded-full bg-engineer-700 text-white text-[10px] font-mono uppercase tracking-wider"
          >
            ENGINEER
          </span>
          <h3 class="text-base font-semibold text-engineer-900">
            {{ t('gate1.hyperparamsTitle') }}
          </h3>
        </div>
        <p class="text-[11px] font-mono text-engineer-700">
          {{ training.hyperparams?.hyperparameters.grounding_source ?? '—' }}
        </p>
      </div>
      <dl class="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-3 text-sm font-mono">
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Epochs</dt>
          <dd class="text-engineer-900 tabular-nums">
            {{ training.hyperparams?.hyperparameters.epochs ?? '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Batch size</dt>
          <dd class="text-engineer-900 tabular-nums">
            {{ training.hyperparams?.hyperparameters.batch_size ?? '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Learning rate</dt>
          <dd class="text-engineer-900 tabular-nums">
            {{ training.hyperparams?.hyperparameters.learning_rate ?? '—' }}
          </dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Aug. intensity</dt>
          <dd class="text-engineer-900">
            {{ training.hyperparams?.hyperparameters.augmentation_intensity ?? '—' }}
          </dd>
        </div>
      </dl>
    </section>

    <footer class="flex items-center justify-between">
      <AppButton variant="ghost" @click="backToLabeling">
        ← {{ t('gate1.backToLabeling') }}
      </AppButton>
      <AppButton :disabled="training.starting || training.loading" @click="approveAndStart">
        {{ training.starting ? t('common.loading') : t('gate1.approveAndStart') }} →
      </AppButton>
    </footer>
  </div>
</template>
