<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import LSFEmbed from '@/components/labeling/LSFEmbed.vue'
import RegionDetailPanel from '@/components/labeling/RegionDetailPanel.vue'
import { useLabelsStore } from '@/stores/labels'
import type { Side } from '@/api/labels'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const labels = useLabelsStore()

const projectId = computed(() => String(route.params.id ?? ''))
const sides: Side[] = ['top', 'bottom']

const selectedRegion = ref<Record<string, unknown> | null>(null)
const draftLsJson = ref<unknown>(null)
const savedNotice = ref<string | null>(null)
const correctedCount = ref(0)

const correctionRun = computed(() => String(route.query.run ?? ''))

onMounted(async () => {
  if (!projectId.value) return
  const corr = route.query.correction === '1'
  const samples = String(route.query.samples ?? '')
    .split(',')
    .filter(Boolean)
  labels.setCorrectionMode(corr, samples)
  await labels.loadTask(projectId.value, 'top')
})

watch(
  () => labels.task,
  () => {
    selectedRegion.value = null
  },
)

function onRegionSelected(region: Record<string, unknown> | null) {
  selectedRegion.value = region
}
function onAnnotationUpdate(ls: unknown) {
  draftLsJson.value = ls
}
async function onAnnotationSubmit(ls: unknown) {
  draftLsJson.value = ls
  await saveCurrent()
}

async function saveCurrent() {
  const payload = draftLsJson.value ?? { result: [] }
  try {
    await labels.submit(payload)
    savedNotice.value = t('labeling.savedAt', { time: new Date().toLocaleTimeString() })
    setTimeout(() => (savedNotice.value = null), 4000)
  } catch {
    /* error already in labels.error */
  }
}

async function refresh() {
  await labels.refreshPredictions()
}
async function selectSide(side: Side) {
  await labels.switchSide(side)
}

function exitCorrectionMode() {
  labels.setCorrectionMode(false, [])
  router.replace({ name: 'labeling', params: { id: projectId.value } })
}

async function continueNext() {
  if (labels.correctionMode) {
    await saveCurrent()
    if (correctionRun.value) {
      await router.push({
        name: 'eval',
        params: { id: projectId.value, runId: correctionRun.value },
      })
    } else {
      exitCorrectionMode()
    }
    return
  }
  await router.push({ name: 'gate1', params: { id: projectId.value } })
}
</script>

<template>
  <div class="h-[calc(100vh-4rem)] flex flex-col bg-surface-sunken">
    <!-- Correction banner -->
    <div
      v-if="labels.correctionMode"
      data-testid="labeling-correction-banner"
      class="flex items-center justify-between gap-4 px-6 py-3 bg-amber-50 border-b border-amber-200 text-amber-900"
    >
      <div class="flex items-center gap-3 min-w-0">
        <span class="h-6 w-6 grid place-items-center rounded-full bg-amber-400 text-white text-xs shrink-0">i</span>
        <p class="text-sm truncate">
          {{
            t('labeling.correctionBanner', {
              count: labels.correctionSampleIds.length,
              run: correctionRun || '—',
            })
          }}
        </p>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <span class="inline-flex items-center h-7 px-3 rounded-full bg-white border border-amber-300 text-xs font-mono text-amber-900">
          {{ t('labeling.correctionCounter', { done: correctedCount, total: labels.correctionSampleIds.length }) }}
        </span>
        <button type="button" class="text-xs font-mono text-amber-800 hover:underline" @click="exitCorrectionMode">
          {{ t('labeling.exitCorrection') }}
        </button>
      </div>
    </div>

    <!-- Action strip -->
    <header
      data-testid="labeling-strip"
      class="flex items-center justify-between gap-4 px-6 py-3 bg-white border-b border-border-default"
    >
      <div class="flex items-center gap-4 min-w-0">
        <span class="inline-flex items-center rounded-lg border border-border-default bg-surface-raised p-0.5 text-sm font-medium">
          <button
            v-for="s in sides"
            :key="s"
            type="button"
            :data-testid="`labeling-side-${s}`"
            class="h-8 px-4 rounded-md transition"
            :class="labels.side === s ? 'bg-white text-ink-900 shadow-card' : 'text-ink-500 hover:text-ink-900'"
            @click="selectSide(s)"
          >
            {{ t(`labeling.side.${s}`) }}
          </button>
        </span>
        <span
          class="inline-flex items-center gap-1.5 h-7 px-2.5 rounded-full text-xs font-medium"
          :class="labels.lastSavedAt ? 'bg-primary-50 text-primary-700' : 'bg-ink-100 text-ink-500'"
        >
          <span class="h-1.5 w-1.5 rounded-full" :class="labels.lastSavedAt ? 'bg-primary-500' : 'bg-ink-400'" />
          {{ labels.lastSavedAt ? t('labeling.saved') : t('labeling.unsaved') }}
        </span>
        <span class="text-xs text-ink-500 font-mono tabular-nums truncate">
          {{ t(`labeling.side.${labels.side}`) }} · {{ labels.designatorCount }} {{ t('labeling.designators') }} ·
          {{ labels.predictionCount }} {{ t('labeling.predictions') }}
        </span>
      </div>

      <div class="flex items-center gap-2 shrink-0">
        <span v-if="savedNotice" class="text-xs font-mono text-primary-700">✓ {{ savedNotice }}</span>
        <span class="hidden md:inline text-[11px] font-mono text-ink-400 border border-border-default rounded px-1.5 py-0.5">
          ⌘R {{ t('labeling.shortcutHint') }}
        </span>
        <AppButton
          data-testid="labeling-refresh"
          variant="secondary"
          size="sm"
          :disabled="labels.refreshing || labels.loading"
          @click="refresh"
        >
          ↻ {{ labels.refreshing ? t('common.loading') : (labels.correctionMode ? t('labeling.refreshShort') : t('labeling.refreshAi')) }}
        </AppButton>
      </div>
    </header>

    <div v-if="labels.error" class="px-6 py-2 bg-red-50 border-b border-red-200 text-sm text-red-700">
      {{ labels.error }}
    </div>

    <!-- Canvas + detail panel -->
    <div class="flex-1 flex min-h-0">
      <div class="flex-1 relative min-w-0">
        <div v-if="labels.loading" class="absolute inset-0 grid place-items-center bg-surface-sunken/80 z-10">
          <p class="text-sm font-mono text-ink-500">{{ t('common.loading') }}</p>
        </div>
        <LSFEmbed
          v-if="labels.task"
          :key="`${projectId}-${labels.side}`"
          :config="labels.task.config"
          :task="labels.task.task"
          @submit="onAnnotationSubmit"
          @update="onAnnotationUpdate"
          @region-selected="onRegionSelected"
        />
        <div v-else-if="!labels.loading" class="absolute inset-0 grid place-items-center p-6">
          <div class="text-center space-y-2">
            <p class="text-sm font-medium text-ink-700">{{ t('labeling.emptyTitle') }}</p>
            <p class="text-xs text-ink-500">{{ t('labeling.emptyHint') }}</p>
          </div>
        </div>
      </div>
      <RegionDetailPanel
        :region="selectedRegion"
        @apply-criteria="() => {}"
        @relate="() => {}"
        @copy="() => {}"
        @toggle-visible="() => {}"
        @delete="() => {}"
      />
    </div>

    <!-- Footer: progress + continue -->
    <footer
      data-testid="labeling-footer"
      class="flex items-center justify-between gap-4 px-6 py-3 bg-white border-t border-border-default"
    >
      <div class="flex items-center gap-4 min-w-0">
        <div class="leading-tight">
          <p class="text-sm font-semibold text-ink-900">
            {{ t('labeling.regionsLabeled', { n: labels.designatorCount }) }}
          </p>
          <p class="text-xs text-ink-500">{{ t('labeling.workflowTip') }}</p>
        </div>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <AppButton variant="ghost" size="sm" @click="router.push({ name: 'dashboard' })">
          {{ t('common.cancel') }}
        </AppButton>
        <AppButton data-testid="labeling-continue" :disabled="labels.submitting" @click="continueNext">
          {{ labels.correctionMode ? t('labeling.saveBackToEval') : t('labeling.continueToTraining') }} →
        </AppButton>
      </div>
    </footer>
  </div>
</template>
