<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useDeployStore } from '@/stores/deploy'
import { useEdgesStore } from '@/stores/edges'
import { useEngineerStore } from '@/stores/engineer'
import { useToastStore } from '@/stores/toast'
import { useEvalStore } from '@/stores/eval'
import { EVAL_THRESHOLDS } from '@/api/eval'
import { getProject } from '@/api/projects'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const deploy = useDeployStore()
const edges = useEdgesStore()
const engineer = useEngineerStore()
const toast = useToastStore()
const evalStore = useEvalStore()

const projectId = computed(() => String(route.params.id ?? ''))
const runId = computed(() => String(route.params.runId ?? ''))
const shortRun = computed(() => runId.value.slice(0, 8))

// PCB slug for the `ais model push --pcb` command — the CLI expects a human
// PCB name, not a UUID. Falls back to the short id only until the project loads.
const pcbName = ref('')

const confirmed = ref(false)
const showModal = ref(false)

onMounted(async () => {
  if (!projectId.value) return
  await edges.fetchAll()
  if (!evalStore.data && runId.value) await evalStore.load(runId.value)
  try {
    pcbName.value = (await getProject(projectId.value)).slug
  } catch {
    pcbName.value = ''
  }
})

function isOnline(lastSeen: string | null): boolean {
  return !!lastSeen && new Date(lastSeen).getTime() >= Date.now() - 5 * 60_000
}
const offlineEdges = computed(() => edges.items.filter((e) => !isOnline(e.last_seen_at)))
const passes = computed(() => evalStore.verdict === 'passed')

const metricTiles = computed(() => {
  const m = evalStore.data?.metrics
  if (!m) return []
  const worst = m.per_component.length ? Math.min(...m.per_component.map((c) => c.f1)) : null
  return [
    { label: 'mAP@0.5', v: m.map, th: EVAL_THRESHOLDS.map_min },
    { label: 'Precision', v: m.precision_macro, th: EVAL_THRESHOLDS.f1_macro_min },
    { label: 'Recall', v: m.recall_macro, th: EVAL_THRESHOLDS.f1_macro_min },
    { label: 'F1 (min)', v: worst, th: EVAL_THRESHOLDS.per_component_f1_min },
  ]
})

async function doPromote() {
  showModal.value = false
  const result = await deploy.promote(projectId.value)
  if (!result) {
    toast.error(t('gate2.promoteFailedTitle'), deploy.error ?? undefined)
    return
  }
  toast.success(t('gate2.promoteSuccessTitle'), t('gate2.promoteSuccessBody', { version: result.model_version }))
  await router.push({ name: 'dashboard' })
}
function backToEval() {
  router.push({ name: 'eval', params: { id: projectId.value, runId: runId.value } })
}
</script>

<template>
  <div class="p-8 max-w-[1280px] mx-auto space-y-6">
    <header>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('gate2.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('gate2.subhead') }}</p>
    </header>

    <!-- Verdict banner -->
    <div
      data-testid="gate2-banner"
      :data-state="passes ? 'passed' : 'blocked'"
      class="flex items-start gap-3 rounded-xl border-2 px-5 py-4"
      :class="passes ? 'bg-primary-50 border-primary-300' : 'bg-red-50 border-red-300'"
    >
      <span class="h-7 w-7 grid place-items-center rounded-full text-white text-sm shrink-0" :class="passes ? 'bg-primary-600' : 'bg-red-500'">
        {{ passes ? '✓' : '✕' }}
      </span>
      <div>
        <p class="text-sm font-semibold text-ink-900">
          {{ passes ? t('gate2.bannerReady', { id: shortRun }) : t('gate2.banner.blocked') }}
        </p>
        <p class="text-sm text-ink-700">{{ passes ? t('gate2.bannerReadyBlurb') : t('gate2.banner.blockedBlurb') }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
      <!-- Model to deploy -->
      <section data-testid="gate2-model" class="rounded-xl bg-white border border-border-default shadow-card p-6">
        <p class="text-sm text-ink-500">{{ t('gate2.modelTitle') }}</p>
        <h2 class="text-xl font-semibold text-ink-900 font-mono">{{ deploy.current?.model_version ?? t('gate2.runLabel', { id: shortRun }) }}</h2>
        <p class="text-xs text-ink-500 mt-1">{{ t('gate2.trainedFrom', { id: shortRun }) }}</p>
        <div class="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div v-for="m in metricTiles" :key="m.label" class="rounded-lg bg-surface-raised p-3">
            <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ m.label }}</p>
            <p class="text-lg font-semibold font-mono tabular-nums" :class="m.v != null && m.v >= m.th ? 'text-primary-700' : 'text-ink-900'">
              {{ m.v == null ? '—' : m.v.toFixed(3) }}
              <span v-if="m.v != null && m.v >= m.th" class="text-primary-600 text-sm">✓</span>
            </p>
          </div>
        </div>
      </section>

      <!-- Target edges -->
      <section data-testid="gate2-edges" class="rounded-xl bg-white border border-border-default shadow-card p-6">
        <header class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold text-ink-900">{{ t('gate2.edgesTitle') }}</h2>
          <span class="text-xs font-mono text-ink-500">{{ t('gate2.unitsCount', { n: edges.items.length }) }}</span>
        </header>
        <ul class="space-y-2">
          <li v-for="edge in edges.items" :key="edge.id" class="flex items-center justify-between gap-3 rounded-lg border border-border-default p-2.5 text-sm">
            <div class="flex items-center gap-2 min-w-0">
              <span class="h-2 w-2 rounded-full shrink-0" :class="isOnline(edge.last_seen_at) ? 'bg-primary-500' : 'bg-red-500'" />
              <p class="font-medium text-ink-900 truncate">{{ edge.name }}</p>
            </div>
            <span class="text-xs font-mono shrink-0" :class="isOnline(edge.last_seen_at) ? 'text-primary-700' : 'text-red-600'">
              {{ isOnline(edge.last_seen_at) ? t('gate2.online') : t('gate2.offline') }}
            </span>
          </li>
          <li v-if="edges.items.length === 0" class="text-sm text-ink-500 text-center py-4">{{ t('gate2.noEdges') }}</li>
        </ul>
      </section>
    </div>

    <!-- What happens -->
    <section data-testid="gate2-whathappens" class="rounded-xl bg-surface-raised border border-border-default p-5">
      <h3 class="text-sm font-semibold text-ink-900 mb-2">{{ t('gate2.whatHappens') }}</h3>
      <ol class="space-y-1.5 text-[13px] text-ink-600 list-decimal list-inside">
        <li>{{ t('gate2.step1') }}</li>
        <li>{{ t('gate2.step2') }}</li>
        <li>{{ t('gate2.step3') }}</li>
      </ol>
    </section>

    <div v-if="offlineEdges.length > 0" class="flex items-start gap-3 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3">
      <span class="h-6 w-6 grid place-items-center rounded-full bg-amber-400 text-white text-xs shrink-0">!</span>
      <p class="text-sm text-amber-900">{{ t('gate2.offlineWarn', { n: offlineEdges.length }) }}</p>
    </div>

    <!-- Confirm checkbox -->
    <section class="rounded-xl bg-white border border-border-default shadow-card p-5">
      <label class="flex items-start gap-3 cursor-pointer">
        <input v-model="confirmed" data-testid="gate2-confirm" type="checkbox" class="mt-1 h-4 w-4 accent-primary-600" />
        <div>
          <p class="text-sm font-medium text-ink-900">{{ t('gate2.confirmRow') }}</p>
          <p class="text-xs text-ink-500">{{ t('gate2.confirmRowBlurb') }}</p>
        </div>
      </label>
    </section>

    <!-- Engineer technical details -->
    <section v-if="engineer.enabled" data-testid="gate2-tech" class="rounded-xl bg-engineer-50 border border-engineer-200 p-5 space-y-3">
      <div class="flex items-center gap-2">
        <span class="inline-flex items-center h-5 px-2 rounded-full bg-engineer-700 text-white text-[10px] font-mono uppercase tracking-wider">ENGINEER</span>
        <h3 class="text-base font-semibold text-engineer-900">{{ t('gate2.techDetailsTitle') }}</h3>
      </div>
      <dl class="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3 text-xs font-mono">
        <div>
          <dt class="text-engineer-700 uppercase">Model SHA256</dt>
          <dd class="text-engineer-900 break-all">{{ deploy.current?.sha256 ?? t('gate2.computedOnPush') }}</dd>
        </div>
        <div>
          <dt class="text-engineer-700 uppercase">Registry tag</dt>
          <dd class="text-engineer-900 break-all">{{ deploy.current?.registry_tag ?? t('gate2.computedOnPush') }}</dd>
        </div>
        <div class="md:col-span-2">
          <dt class="text-engineer-700 uppercase">Rollback target</dt>
          <dd class="text-engineer-900">{{ t('gate2.rollbackTarget') }}</dd>
        </div>
      </dl>
      <div class="bg-engineer-900 rounded-lg p-3 font-mono text-[11px] text-engineer-200">
        <p class="text-engineer-200/60">$ {{ t('gate2.pushCommand') }}</p>
        <p>ais model push --pcb {{ pcbName || projectId.slice(0, 8) }} --tag &lt;tag&gt;</p>
      </div>
    </section>

    <footer class="flex items-center justify-between rounded-xl bg-white border border-border-default shadow-card px-6 py-4">
      <AppButton data-testid="gate2-back" variant="secondary" @click="backToEval">← {{ t('gate2.backToEval') }}</AppButton>
      <AppButton data-testid="gate2-deploy" :disabled="!passes || !confirmed || deploy.promoting" @click="showModal = true">
        {{ deploy.promoting ? t('common.loading') : t('gate2.deploy') }} →
      </AppButton>
    </footer>

    <!-- Confirm modal -->
    <div v-if="showModal" class="fixed inset-0 bg-ink-900/60 backdrop-blur-sm grid place-items-center p-4 z-50" @click.self="showModal = false">
      <div class="bg-white rounded-2xl shadow-pop max-w-md w-full p-6 space-y-4">
        <h3 class="text-lg font-semibold text-ink-900">{{ t('gate2.modal.title') }}</h3>
        <p class="text-sm text-ink-600">{{ t('gate2.modal.body') }}</p>
        <div class="flex items-center justify-end gap-2 pt-2">
          <AppButton variant="ghost" @click="showModal = false">{{ t('common.cancel') }}</AppButton>
          <AppButton data-testid="gate2-modal-confirm" @click="doPromote">{{ t('gate2.modal.confirm') }}</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>
