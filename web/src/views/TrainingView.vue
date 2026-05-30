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
const shortRun = computed(() => runId.value.slice(0, 8))

onMounted(async () => {
  if (!runId.value) return
  await training.loadRun(projectId.value, runId.value)
  training.openStream(runId.value)
})
onBeforeUnmount(() => training.closeStream())

const statusTone: Record<string, string> = {
  pending: 'bg-ink-100 text-ink-600',
  running: 'bg-primary-50 text-primary-700',
  succeeded: 'bg-primary-50 text-primary-700',
  failed: 'bg-red-50 text-red-700',
  cancelled: 'bg-ink-100 text-ink-600',
}

function fmtEta(s: number | null): string {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  return m > 0 ? `~${m} ${t('training.min')}` : `~${s}s`
}
function fmtMetric(v: number | null, digits = 3): string {
  return v == null ? '—' : v.toFixed(digits)
}
function startedTime(): string {
  const s = training.currentRun?.started_at
  if (!s) return '—'
  try {
    return new Date(s).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return '—'
  }
}

const buckets = computed(() =>
  training.perComponent.reduce(
    (acc, c) => ((acc[c.state]++, acc)),
    { queued: 0, training: 0, done: 0 } as Record<string, number>,
  ),
)

const gpuLabel = computed(() => {
  const u = training.live.gpu_mem_used_gb
  const tot = training.live.gpu_mem_total_gb
  if (u == null || tot == null) return '—'
  return `${u} / ${tot} GB · ${Math.round((u / tot) * 100)}%`
})

async function cancel() {
  training.closeStream()
  await router.push({ name: 'dashboard' })
}
async function viewResults() {
  await router.push({ name: 'setup-eval', params: { id: projectId.value, runId: runId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <!-- Header -->
    <header data-testid="training-header" class="flex items-start justify-between gap-4 flex-wrap">
      <div class="space-y-1">
        <h1 class="text-2xl font-semibold text-ink-900">
          {{ t('training.runTitle', { id: shortRun }) }}
        </h1>
        <p class="text-sm text-ink-500 font-mono">
          {{ t('training.startedLine', { time: startedTime(), epoch: training.live.epoch, total: training.live.total_epochs }) }}
          · {{ t('training.eta') }} {{ fmtEta(training.live.eta_seconds) }}
        </p>
      </div>
      <span
        data-testid="training-status"
        class="inline-flex items-center gap-1.5 h-7 px-3 rounded-full text-xs font-medium"
        :class="statusTone[training.status]"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="training.status === 'failed' ? 'bg-red-500' : 'bg-primary-500'" />
        {{ t(`training.status.${training.status}`) }}
      </span>
    </header>

    <!-- Progress strip -->
    <section data-testid="training-progress" class="rounded-xl bg-white border border-border-default shadow-card p-5 flex items-center gap-6 flex-wrap">
      <div class="shrink-0">
        <p class="text-base font-semibold text-ink-900">
          {{ t('training.epoch') }} {{ training.live.epoch }} / {{ training.live.total_epochs }}
        </p>
        <p class="text-xs text-ink-500 font-mono">
          {{ training.streaming ? t('training.streaming') : t('training.idle') }}
        </p>
      </div>
      <div class="flex-1 min-w-[200px]">
        <div class="h-2.5 rounded-full bg-ink-100 overflow-hidden">
          <div class="h-full bg-primary-500 transition-all" :style="{ width: `${training.progressPct}%` }" />
        </div>
        <p class="mt-1 text-xs text-primary-700 font-mono">{{ training.progressPct }}%</p>
      </div>
      <div class="rounded-lg bg-primary-50 px-4 py-2 shrink-0">
        <p class="text-[11px] font-mono uppercase tracking-wider text-primary-700">{{ t('training.estFinish') }}</p>
        <p class="text-lg font-semibold font-mono text-primary-800">{{ fmtEta(training.live.eta_seconds) }}</p>
      </div>
    </section>

    <div v-if="training.error" class="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
      {{ training.error }}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start">
      <!-- Per-component -->
      <section data-testid="training-percomp" class="rounded-xl bg-white border border-border-default shadow-card p-6">
        <div class="flex items-start justify-between mb-3">
          <div>
            <h2 class="text-base font-semibold text-ink-900">{{ t('training.perCompTitle') }}</h2>
            <p class="text-xs text-ink-500">{{ t('training.perCompSub', { n: training.perComponent.length }) }}</p>
          </div>
          <div class="flex items-center gap-3 text-xs font-mono shrink-0">
            <span class="text-primary-700">✓ {{ buckets.done }}</span>
            <span class="text-info">↻ {{ buckets.training }}</span>
            <span class="text-ink-400">· {{ buckets.queued }}</span>
          </div>
        </div>
        <div class="rounded-lg border border-border-default overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-surface-raised text-[11px] font-mono uppercase tracking-wider text-ink-500">
              <tr>
                <th class="text-left px-4 py-2.5 font-medium">{{ t('training.colDesignator') }}</th>
                <th class="text-left px-4 py-2.5 font-medium">{{ t('training.colState') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in training.perComponent" :key="c.designator" class="border-t border-border-subtle">
                <td class="px-4 py-2.5 font-mono">{{ c.designator }}</td>
                <td class="px-4 py-2.5">
                  <span
                    class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
                    :class="c.state === 'done' ? 'bg-primary-50 text-primary-700' : c.state === 'training' ? 'bg-blue-50 text-info' : 'bg-ink-100 text-ink-500'"
                  >
                    {{ t(`training.state.${c.state}`) }}
                  </span>
                </td>
              </tr>
              <tr v-if="training.perComponent.length === 0" class="border-t border-border-subtle">
                <td colspan="2" class="px-4 py-6 text-center text-sm text-ink-500">{{ t('training.noComponents') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="space-y-6">
        <!-- Engineer internals (real live-derived only) -->
        <section
          v-if="engineer.enabled"
          data-testid="training-internals"
          class="rounded-xl bg-engineer-50 border border-engineer-200 p-5 space-y-3"
        >
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center h-5 px-2 rounded-full bg-engineer-700 text-white text-[10px] font-mono uppercase tracking-wider">ENGINEER</span>
            <h3 class="text-base font-semibold text-engineer-900">{{ t('training.techDetailsTitle') }}</h3>
          </div>
          <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm font-mono">
            <div class="flex justify-between"><dt class="text-engineer-700">Epochs</dt><dd class="text-engineer-900 tabular-nums">{{ training.live.total_epochs }}</dd></div>
            <div class="flex justify-between"><dt class="text-engineer-700">Loss</dt><dd class="text-engineer-900 tabular-nums">{{ fmtMetric(training.live.loss) }}</dd></div>
            <div class="flex justify-between col-span-2"><dt class="text-engineer-700">GPU</dt><dd class="text-engineer-900 tabular-nums">{{ gpuLabel }}</dd></div>
          </dl>
          <div class="bg-engineer-900 rounded-lg p-3 font-mono text-[11px] text-engineer-200 max-h-32 overflow-y-auto">
            <p v-if="training.logLines.length === 0" class="text-engineer-200/50">{{ t('training.waitingForLogs') }}</p>
            <p v-for="(line, i) in training.logLines.slice(-12)" :key="i">{{ line }}</p>
          </div>
        </section>

        <!-- Live metrics -->
        <section data-testid="training-metrics" class="rounded-xl bg-white border border-border-default shadow-card p-6">
          <h2 class="text-base font-semibold text-ink-900">{{ t('training.liveMetrics') }}</h2>
          <p class="text-xs text-ink-500 mb-3">{{ t('training.liveMetricsSub') }}</p>
          <div class="grid grid-cols-2 gap-3">
            <div
v-for="m in [
              { label: 'mAP', v: training.live.map },
              { label: 'F1 macro', v: training.live.f1 },
              { label: 'Precision', v: training.live.precision },
              { label: 'Recall', v: training.live.recall },
            ]" :key="m.label" class="rounded-lg bg-surface-raised p-3">
              <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ m.label }}</p>
              <p class="text-2xl font-semibold font-mono tabular-nums text-ink-900">{{ fmtMetric(m.v) }}</p>
            </div>
          </div>
        </section>

        <!-- Things to know (factual, not fabricated data) -->
        <section data-testid="training-things" class="rounded-xl bg-surface-raised border border-border-default p-5">
          <h3 class="text-sm font-semibold text-ink-900 mb-2">{{ t('training.thingsTitle') }}</h3>
          <ul class="space-y-2 text-[13px] text-ink-600">
            <li class="flex gap-2"><span class="text-ink-400 mt-0.5">·</span><span>{{ t('training.thing1') }}</span></li>
            <li class="flex gap-2"><span class="text-ink-400 mt-0.5">·</span><span>{{ t('training.thing2') }}</span></li>
            <li class="flex gap-2"><span class="text-ink-400 mt-0.5">·</span><span>{{ t('training.thing3') }}</span></li>
          </ul>
        </section>
      </div>
    </div>

    <footer class="flex items-center justify-between rounded-xl bg-white border border-border-default shadow-card px-6 py-4">
      <AppButton variant="secondary" @click="cancel">{{ t('training.cancel') }}</AppButton>
      <AppButton data-testid="training-results" :disabled="training.status !== 'succeeded'" @click="viewResults">
        {{ t('training.viewResults') }} →
      </AppButton>
    </footer>
  </div>
</template>
