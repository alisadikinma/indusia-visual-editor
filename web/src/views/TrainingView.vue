<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
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
const runId = computed(() => String(route.params.runId ?? ''))

onMounted(async () => {
  if (!runId.value) return
  await training.loadRun(projectId.value, runId.value)
  training.openStream(runId.value)
})

onBeforeUnmount(() => {
  training.closeStream()
})

const statusTone: Record<string, string> = {
  pending: 'bg-ink-100 text-ink-700',
  running: 'bg-info/10 text-info border border-info/30',
  succeeded: 'bg-success/10 text-success border border-success/30',
  failed: 'bg-danger/10 text-danger border border-danger/30',
  cancelled: 'bg-ink-100 text-ink-600',
}

function fmtEta(s: number | null): string {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  return m > 0 ? `~${m} min` : `~${s}s`
}

function fmtMetric(v: number | null, digits = 3): string {
  return v == null ? '—' : v.toFixed(digits)
}

const componentBuckets = computed(() => {
  return training.perComponent.reduce(
    (acc, c) => {
      acc[c.state]++
      return acc
    },
    { queued: 0, training: 0, done: 0 } as Record<string, number>,
  )
})

async function cancel() {
  training.closeStream()
  await router.push({ name: 'dashboard' })
}

async function viewResults() {
  await router.push({
    name: 'setup-eval',
    params: { id: projectId.value, runId: runId.value },
  })
}
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="flex items-start justify-between gap-4 flex-wrap">
      <div class="space-y-1">
        <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
          {{ t('training.kicker') }}
        </p>
        <h1 class="text-2xl font-semibold text-ink-900">{{ t('training.title') }}</h1>
      </div>
      <span
        class="inline-flex items-center h-7 px-3 rounded-full text-xs font-mono uppercase tracking-wider"
        :class="statusTone[training.status]"
      >
        ● {{ t(`training.status.${training.status}`) }}
      </span>
    </header>

    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
      <div class="flex items-center justify-between text-sm font-mono">
        <span class="text-ink-700 font-medium">
          {{ t('training.epoch') }} {{ training.live.epoch }} / {{ training.live.total_epochs }}
        </span>
        <span class="text-ink-500">ETA {{ fmtEta(training.live.eta_seconds) }}</span>
      </div>
      <div class="mt-3 h-2 rounded-full bg-ink-100 overflow-hidden">
        <div
          class="h-full bg-primary-700 transition-all"
          :style="{ width: `${training.progressPct}%` }"
        />
      </div>
      <p class="mt-2 text-xs text-ink-500 font-mono">
        {{ training.progressPct }}% ·
        {{ training.streaming ? t('training.streaming') : t('training.idle') }}
      </p>
    </section>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <section class="lg:col-span-2 rounded-xl bg-white border border-ink-200 shadow-card p-5">
        <header class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold text-ink-900">{{ t('training.perCompTitle') }}</h2>
          <div class="flex items-center gap-3 text-xs font-mono">
            <span class="text-success">✓ {{ componentBuckets.done }} {{ t('training.done') }}</span>
            <span class="text-info">↻ {{ componentBuckets.training }} {{ t('training.training') }}</span>
            <span class="text-ink-500">· {{ componentBuckets.queued }} {{ t('training.queued') }}</span>
          </div>
        </header>
        <div class="rounded-lg border border-ink-200 overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-ink-50 text-xs font-mono uppercase tracking-wider text-ink-500">
              <tr>
                <th class="text-left px-4 py-2 font-medium">{{ t('training.colDesignator') }}</th>
                <th class="text-left px-4 py-2 font-medium">{{ t('training.colState') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="c in training.perComponent"
                :key="c.designator"
                class="border-t border-ink-100"
              >
                <td class="px-4 py-2 font-mono">{{ c.designator }}</td>
                <td class="px-4 py-2">
                  <span
                    class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                    :class="
                      c.state === 'done'
                        ? 'bg-success/10 text-success'
                        : c.state === 'training'
                          ? 'bg-info/10 text-info'
                          : 'bg-ink-100 text-ink-500'
                    "
                  >
                    {{ t(`training.state.${c.state}`) }}
                  </span>
                </td>
              </tr>
              <tr v-if="training.perComponent.length === 0" class="border-t border-ink-100">
                <td colspan="2" class="px-4 py-6 text-center text-sm text-ink-500">
                  {{ t('training.noComponents') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5">
        <h2 class="text-base font-semibold text-ink-900 mb-3">
          {{ t('training.liveMetrics') }}
        </h2>
        <dl class="space-y-3 font-mono">
          <div class="flex justify-between text-sm">
            <dt class="text-ink-500">mAP</dt>
            <dd class="text-ink-900 tabular-nums">{{ fmtMetric(training.live.map) }}</dd>
          </div>
          <div class="flex justify-between text-sm">
            <dt class="text-ink-500">F1</dt>
            <dd class="text-ink-900 tabular-nums">{{ fmtMetric(training.live.f1) }}</dd>
          </div>
          <div class="flex justify-between text-sm">
            <dt class="text-ink-500">Precision</dt>
            <dd class="text-ink-900 tabular-nums">{{ fmtMetric(training.live.precision) }}</dd>
          </div>
          <div class="flex justify-between text-sm">
            <dt class="text-ink-500">Recall</dt>
            <dd class="text-ink-900 tabular-nums">{{ fmtMetric(training.live.recall) }}</dd>
          </div>
          <div class="flex justify-between text-sm border-t border-ink-100 pt-3">
            <dt class="text-ink-500">Loss</dt>
            <dd class="text-ink-900 tabular-nums">{{ fmtMetric(training.live.loss) }}</dd>
          </div>
        </dl>
      </section>
    </div>

    <section
      v-if="engineer.enabled"
      class="rounded-xl bg-engineer-50 border border-engineer-200 p-5 space-y-4"
    >
      <div class="flex items-center gap-2">
        <span
          class="inline-flex items-center h-5 px-2 rounded-full bg-engineer-700 text-white text-[10px] font-mono uppercase tracking-wider"
        >
          ENGINEER
        </span>
        <h3 class="text-base font-semibold text-engineer-900">
          {{ t('training.techDetailsTitle') }}
        </h3>
      </div>
      <dl class="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-3 text-sm font-mono">
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Optimizer</dt>
          <dd class="text-engineer-900">AdamW</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">LR</dt>
          <dd class="text-engineer-900 tabular-nums">0.001 cosine</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">Batch</dt>
          <dd class="text-engineer-900 tabular-nums">32</dd>
        </div>
        <div>
          <dt class="text-engineer-700 text-xs uppercase">GPU</dt>
          <dd class="text-engineer-900 tabular-nums">
            {{
              training.live.gpu_mem_used_gb != null
                ? `${training.live.gpu_mem_used_gb}/${training.live.gpu_mem_total_gb} GB`
                : '—'
            }}
          </dd>
        </div>
      </dl>
      <div
        class="bg-engineer-900 rounded-lg p-3 font-mono text-[11px] text-engineer-200 max-h-32 overflow-y-auto"
      >
        <p v-if="training.logLines.length === 0" class="text-engineer-200/50">
          {{ t('training.waitingForLogs') }}
        </p>
        <p v-for="(line, i) in training.logLines.slice(-12)" :key="i">{{ line }}</p>
      </div>
    </section>

    <footer class="flex items-center justify-between">
      <AppButton variant="ghost" @click="cancel">{{ t('training.cancel') }}</AppButton>
      <AppButton :disabled="training.status !== 'succeeded'" @click="viewResults">
        {{ t('training.viewResults') }} →
      </AppButton>
    </footer>
  </div>
</template>
