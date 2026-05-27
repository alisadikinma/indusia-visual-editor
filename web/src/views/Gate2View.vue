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

const confirmed = ref(false)
const showModal = ref(false)

onMounted(async () => {
  if (!projectId.value) return
  await edges.fetchAll()
  if (!evalStore.data && runId.value) await evalStore.load(runId.value)
})

const offlineEdges = computed(() =>
  edges.items.filter((e) => {
    if (!e.last_seen_at) return true
    return new Date(e.last_seen_at).getTime() < Date.now() - 5 * 60_000
  }),
)

const passes = computed(() => evalStore.verdict === 'passed')

async function doPromote() {
  showModal.value = false
  const result = await deploy.promote(projectId.value)
  if (!result) {
    toast.error(t('gate2.promoteFailedTitle'), deploy.error ?? undefined)
    return
  }
  toast.success(
    t('gate2.promoteSuccessTitle'),
    t('gate2.promoteSuccessBody', { version: result.model_version }),
  )
  await router.push({ name: 'dashboard' })
}

function backToEval() {
  router.push({
    name: 'eval',
    params: { id: projectId.value, runId: runId.value },
  })
}
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('gate2.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('gate2.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('gate2.subhead') }}</p>
    </header>

    <div
      v-if="passes"
      class="rounded-xl bg-primary-50 border border-primary-200 px-5 py-4 flex items-start gap-3"
    >
      <span class="h-6 w-6 rounded-full bg-primary-700 text-white grid place-items-center text-xs shrink-0">
        ✓
      </span>
      <div class="flex-1">
        <p class="text-sm font-semibold text-primary-900">{{ t('gate2.banner.passed') }}</p>
        <p class="text-sm text-primary-900/80">{{ t('gate2.banner.passedBlurb') }}</p>
      </div>
    </div>
    <div
      v-else
      class="rounded-xl bg-red-50 border border-red-200 px-5 py-4 flex items-start gap-3"
    >
      <span class="h-6 w-6 rounded-full bg-red-700 text-white grid place-items-center text-xs shrink-0">
        ✕
      </span>
      <div class="flex-1">
        <p class="text-sm font-semibold text-red-900">{{ t('gate2.banner.blocked') }}</p>
        <p class="text-sm text-red-900/80">{{ t('gate2.banner.blockedBlurb') }}</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <section class="lg:col-span-2 rounded-xl bg-white border border-ink-200 shadow-card p-5 space-y-4">
        <h2 class="text-base font-semibold text-ink-900">{{ t('gate2.modelTitle') }}</h2>
        <dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">mAP</dt>
            <dd class="font-mono text-ink-900">{{ ((evalStore.data?.metrics.map ?? 0) * 100).toFixed(1) }}%</dd>
          </div>
          <div>
            <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">F1 macro</dt>
            <dd class="font-mono text-ink-900">
              {{ ((evalStore.data?.metrics.f1_macro ?? 0) * 100).toFixed(1) }}%
            </dd>
          </div>
          <div>
            <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">FP / FN</dt>
            <dd class="font-mono text-ink-900">
              {{ evalStore.data?.metrics.false_positives ?? 0 }} / {{ evalStore.data?.metrics.false_negatives ?? 0 }}
            </dd>
          </div>
          <div>
            <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('gate2.runId') }}</dt>
            <dd class="font-mono text-ink-700 text-xs truncate">{{ runId }}</dd>
          </div>
        </dl>

        <h3 class="text-sm font-semibold text-ink-900 mt-4">{{ t('gate2.whatHappens') }}</h3>
        <ol class="space-y-2 text-sm text-ink-600 list-decimal list-inside">
          <li>{{ t('gate2.step1') }}</li>
          <li>{{ t('gate2.step2') }}</li>
          <li>{{ t('gate2.step3') }}</li>
        </ol>
      </section>

      <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5 space-y-3">
        <header class="flex items-center justify-between">
          <h2 class="text-base font-semibold text-ink-900">{{ t('gate2.edgesTitle') }}</h2>
          <span class="text-xs font-mono text-ink-500">
            {{ edges.onlineCount }}/{{ edges.items.length }} {{ t('gate2.online') }}
          </span>
        </header>
        <ul class="space-y-2">
          <li
            v-for="edge in edges.items"
            :key="edge.id"
            class="flex items-center justify-between rounded-lg border border-ink-200 p-2.5 text-sm"
          >
            <div class="min-w-0">
              <p class="font-medium text-ink-900 truncate">{{ edge.name }}</p>
              <p class="text-xs font-mono text-ink-500 truncate">{{ edge.webhook_url }}</p>
            </div>
            <span
              class="inline-flex items-center h-5 px-2 rounded-full text-[11px] font-medium"
              :class="
                edge.last_seen_at && new Date(edge.last_seen_at).getTime() >= Date.now() - 5 * 60_000
                  ? 'bg-success/10 text-success'
                  : 'bg-ink-100 text-ink-500'
              "
            >
              {{ edge.last_seen_at && new Date(edge.last_seen_at).getTime() >= Date.now() - 5 * 60_000 ? '●' : '○' }}
              {{
                edge.last_seen_at && new Date(edge.last_seen_at).getTime() >= Date.now() - 5 * 60_000
                  ? t('gate2.online')
                  : t('gate2.offline')
              }}
            </span>
          </li>
          <li v-if="edges.items.length === 0" class="text-sm text-ink-500 text-center py-4">
            {{ t('gate2.noEdges') }}
          </li>
        </ul>
        <p
          v-if="offlineEdges.length > 0"
          class="rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-800"
        >
          {{ t('gate2.offlineWarn', { n: offlineEdges.length }) }}
        </p>
      </section>
    </div>

    <section
      v-if="engineer.enabled"
      class="rounded-xl bg-engineer-50 border border-engineer-200 p-5 space-y-3"
    >
      <div class="flex items-center gap-2">
        <span
          class="inline-flex items-center h-5 px-2 rounded-full bg-engineer-700 text-white text-[10px] font-mono uppercase tracking-wider"
        >
          ENGINEER
        </span>
        <h3 class="text-base font-semibold text-engineer-900">
          {{ t('gate2.techDetailsTitle') }}
        </h3>
      </div>
      <dl class="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3 text-xs font-mono">
        <div>
          <dt class="text-engineer-700 uppercase">Model SHA256</dt>
          <dd class="text-engineer-900 break-all">
            {{ deploy.current?.sha256 ?? 'b3f9c1…42de7a (computed on push)' }}
          </dd>
        </div>
        <div>
          <dt class="text-engineer-700 uppercase">Registry tag</dt>
          <dd class="text-engineer-900">
            {{ deploy.current?.registry_tag ?? '<derived from train_run end ts + run id>' }}
          </dd>
        </div>
        <div class="md:col-span-2">
          <dt class="text-engineer-700 uppercase">Rollback target</dt>
          <dd class="text-engineer-900">{{ t('gate2.rollbackTarget') }}</dd>
        </div>
      </dl>
      <div class="bg-engineer-900 rounded-lg p-3 font-mono text-[11px] text-engineer-200">
        <p class="text-engineer-200/60">$ {{ t('gate2.pushCommand') }}</p>
        <p>{{ deploy.current?.push_command ?? `ais model push --pcb ${projectId.slice(0, 8)} --tag <tag>` }}</p>
      </div>
    </section>

    <section class="rounded-xl bg-ink-50 border border-ink-200 p-5">
      <label class="flex items-start gap-3 cursor-pointer">
        <input v-model="confirmed" type="checkbox" class="mt-1 h-4 w-4" />
        <div>
          <p class="text-sm font-medium text-ink-900">{{ t('gate2.confirmRow') }}</p>
          <p class="text-xs text-ink-500">{{ t('gate2.confirmRowBlurb') }}</p>
        </div>
      </label>
    </section>

    <footer class="flex items-center justify-between">
      <AppButton variant="ghost" @click="backToEval">← {{ t('gate2.backToEval') }}</AppButton>
      <AppButton :disabled="!passes || !confirmed || deploy.promoting" @click="showModal = true">
        {{ deploy.promoting ? t('common.loading') : t('gate2.deploy') }} →
      </AppButton>
    </footer>

    <!-- Promote confirmation modal -->
    <div
      v-if="showModal"
      class="fixed inset-0 bg-ink-900/60 backdrop-blur-sm grid place-items-center p-4 z-50"
      @click.self="showModal = false"
    >
      <div class="bg-white rounded-2xl shadow-pop max-w-md w-full p-6 space-y-4">
        <h3 class="text-lg font-semibold text-ink-900">{{ t('gate2.modal.title') }}</h3>
        <p class="text-sm text-ink-600">{{ t('gate2.modal.body') }}</p>
        <div class="flex items-center justify-end gap-2 pt-2">
          <AppButton variant="ghost" @click="showModal = false">{{ t('common.cancel') }}</AppButton>
          <AppButton @click="doPromote">{{ t('gate2.modal.confirm') }}</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>
