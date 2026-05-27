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

onMounted(async () => {
  if (!projectId.value) return
  // Optional correction-mode query: ?correction=1&samples=id1,id2
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
    savedNotice.value = t('labeling.savedAt', {
      time: new Date().toLocaleTimeString(),
    })
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
</script>

<template>
  <div class="h-[calc(100vh-4rem)] flex flex-col bg-ink-50">
    <!-- Banner: correction mode -->
    <div
      v-if="labels.correctionMode"
      class="flex items-center justify-between gap-4 px-6 py-3 bg-amber-50 border-b border-amber-200 text-amber-900"
    >
      <div class="flex items-center gap-3">
        <span class="font-mono text-xs uppercase tracking-wider text-amber-700">
          {{ t('labeling.correctionLabel') }}
        </span>
        <p class="text-sm">
          {{
            t('labeling.correctionMessage', {
              count: labels.correctionSampleIds.length,
            })
          }}
        </p>
      </div>
      <button
        type="button"
        class="text-xs font-mono text-amber-800 hover:underline"
        @click="exitCorrectionMode"
      >
        {{ t('labeling.exitCorrection') }}
      </button>
    </div>

    <!-- Action strip -->
    <header
      class="flex items-center justify-between gap-4 px-6 py-3 bg-white border-b border-ink-200"
    >
      <div class="flex items-center gap-4 min-w-0">
        <h1 class="text-base font-semibold text-ink-900 truncate">
          {{ t('labeling.title') }}
        </h1>
        <span
          class="inline-flex items-center rounded-full border border-ink-200 bg-ink-50 p-0.5 text-xs font-mono"
        >
          <button
            v-for="s in sides"
            :key="s"
            type="button"
            class="h-7 px-3 rounded-full transition capitalize"
            :class="
              labels.side === s
                ? 'bg-white text-ink-900 shadow-card'
                : 'text-ink-500 hover:text-ink-900'
            "
            @click="selectSide(s)"
          >
            {{ t(`labeling.side.${s}`) }}
          </button>
        </span>
        <span class="text-xs text-ink-500 font-mono tabular-nums">
          {{ labels.designatorCount }} {{ t('labeling.designators') }} ·
          {{ labels.predictionCount }} {{ t('labeling.predictions') }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <span v-if="savedNotice" class="text-xs font-mono text-primary-700">
          ✓ {{ savedNotice }}
        </span>
        <AppButton
          variant="ghost"
          size="sm"
          :disabled="labels.refreshing || labels.loading"
          @click="refresh"
        >
          {{ labels.refreshing ? t('common.loading') : t('labeling.refreshAi') }}
        </AppButton>
        <AppButton
          size="sm"
          :disabled="labels.submitting || !labels.task"
          @click="saveCurrent"
        >
          {{ labels.submitting ? t('common.loading') : t('labeling.save') }}
        </AppButton>
      </div>
    </header>

    <!-- Loading + error states -->
    <div
      v-if="labels.error"
      class="px-6 py-2 bg-red-50 border-b border-red-200 text-sm text-red-700"
    >
      {{ labels.error }}
    </div>

    <!-- Main 2-pane: LSF canvas + detail panel -->
    <div class="flex-1 flex min-h-0">
      <div class="flex-1 relative min-w-0">
        <div
          v-if="labels.loading"
          class="absolute inset-0 grid place-items-center bg-ink-50/80 z-10"
        >
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
        <div
          v-else-if="!labels.loading"
          class="absolute inset-0 grid place-items-center p-6"
        >
          <div class="text-center space-y-2">
            <p class="text-sm font-medium text-ink-700">{{ t('labeling.emptyTitle') }}</p>
            <p class="text-xs text-ink-500">{{ t('labeling.emptyHint') }}</p>
          </div>
        </div>
      </div>
      <RegionDetailPanel :region="selectedRegion" />
    </div>

    <!-- Workflow tip -->
    <footer
      class="px-6 py-2 bg-white border-t border-ink-200 text-xs font-mono text-ink-500"
    >
      {{ t('labeling.workflowTip') }}
    </footer>
  </div>
</template>
