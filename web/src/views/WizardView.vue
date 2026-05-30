<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useWizardStore } from '@/stores/wizard'
import { useProjectsStore } from '@/stores/projects'
import type { AssetKind, GoldenQc, QcVerdict } from '@/api/assets'

const previewUrls = reactive<Partial<Record<AssetKind, string>>>({})
const dimensions = reactive<Partial<Record<AssetKind, { w: number; h: number }>>>({})
const fileNames = reactive<Partial<Record<AssetKind, string>>>({})
const bottomSkipped = ref(false)

function readDimensions(kind: AssetKind, url: string) {
  const img = new Image()
  img.onload = () => {
    dimensions[kind] = { w: img.naturalWidth, h: img.naturalHeight }
  }
  img.src = url
}

function formatBytes(n: number | null | undefined): string {
  if (n == null) return ''
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

interface StepDef {
  key: 'project' | 'bom' | 'golden' | 'drawing' | 'review'
  stepKey: string
  titleKey: string
  blurbKey: string
}

const STEPS: StepDef[] = [
  { key: 'project', stepKey: 'wizard.step1', titleKey: 'wizard.s1Title', blurbKey: 'wizard.s1Blurb' },
  { key: 'bom', stepKey: 'wizard.step2', titleKey: 'wizard.s2Title', blurbKey: 'wizard.s2Blurb' },
  { key: 'golden', stepKey: 'wizard.step3', titleKey: 'wizard.s3Title', blurbKey: 'wizard.s3Blurb' },
  { key: 'drawing', stepKey: 'wizard.step4', titleKey: 'wizard.s4Title', blurbKey: 'wizard.s4Blurb' },
  { key: 'review', stepKey: 'wizard.step5', titleKey: 'wizard.s5Title', blurbKey: 'wizard.s5Blurb' },
]

// Example PCB layout schematic (decorative — clearly labelled EXAMPLE). Boxes
// are placed on a normalized 0–100 grid so the illustration scales fluidly.
const EXAMPLE_PARTS = [
  { id: 'R1', x: 4, y: 14, w: 16, h: 12 },
  { id: 'C4', x: 26, y: 12, w: 9, h: 22 },
  { id: 'U7', x: 41, y: 22, w: 18, h: 30 },
  { id: 'D2', x: 66, y: 12, w: 12, h: 12 },
  { id: 'J3', x: 4, y: 52, w: 20, h: 16 },
  { id: 'U8', x: 70, y: 46, w: 16, h: 22 },
  { id: 'R6', x: 44, y: 72, w: 22, h: 9 },
]

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const wizard = useWizardStore()
const projects = useProjectsStore()

const stepIndex = computed(() => wizard.stepIndex)
const current = computed(() => STEPS[stepIndex.value])
const miCount = computed(() => wizard.bomItems.filter((i) => i.mi_likely).length)

const idParam = computed(() => String(route.params.id ?? ''))

onMounted(async () => {
  if (idParam.value === 'new' || idParam.value === '') {
    wizard.reset()
    return
  }
  if (wizard.project?.id !== idParam.value) {
    wizard.reset()
    if (!projects.items.length) await projects.fetchAll()
    const existing = projects.items.find((p) => p.id === idParam.value)
    if (existing) wizard.hydrateFromExisting(existing)
  }
})

// After project creation, rewrite URL to include the real id.
watch(
  () => wizard.projectId,
  (id) => {
    if (id && idParam.value === 'new') {
      router.replace({ name: 'wizard', params: { id }, query: route.query })
    }
  },
)

async function handleNext() {
  try {
    await wizard.next()
  } catch {
    /* error displayed inline */
  }
}

async function handleFinish() {
  if (!wizard.projectId) return
  await router.push({ name: 'labeling', params: { id: wizard.projectId } })
}

// Jump to an already-reached step (used by the review "Edit" buttons).
function goToStep(index: number) {
  if (index >= 0 && index < STEPS.length) wizard.stepIndex = index
}

async function onFile(kind: AssetKind, e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!wizard.project) {
    wizard.error = t('wizard.errMissingProject')
    return
  }
  if (file.type.startsWith('image/')) {
    if (previewUrls[kind]) URL.revokeObjectURL(previewUrls[kind]!)
    const url = URL.createObjectURL(file)
    previewUrls[kind] = url
    fileNames[kind] = file.name
    delete dimensions[kind]
    readDimensions(kind, url)
  } else {
    fileNames[kind] = file.name
  }
  if (kind === 'golden_bottom') bottomSkipped.value = false
  try {
    await wizard.uploadAsset(kind, file)
  } catch {
    /* error displayed inline */
  } finally {
    input.value = ''
  }
}

onUnmounted(() => {
  for (const url of Object.values(previewUrls)) {
    if (url) URL.revokeObjectURL(url)
  }
})

const assetName = (kind: AssetKind): string | null => {
  const a = wizard.assets[kind]
  if (!a) return null
  return fileNames[kind] ?? a.path.split('/').pop() ?? a.path
}

function dimLabel(kind: AssetKind): string {
  const d = dimensions[kind]
  return d ? `${d.w}×${d.h} px` : ''
}

function qcTone(v: QcVerdict): string {
  return {
    ok: 'bg-primary-50 text-primary-800',
    warn: 'bg-amber-50 text-amber-800',
    fail: 'bg-red-50 text-red-700',
  }[v]
}

function qcTitle(qc: GoldenQc): string {
  const reasons = qc.reasons.length
    ? qc.reasons.map((r) => t(`wizard.qcReason.${r}`)).join(', ')
    : t('wizard.qc.ok')
  return `${reasons} · sharpness ${qc.sharpness} · luma ${qc.mean_luminance}`
}

// Review summary rows — only honest, present fields are surfaced.
const reviewRows = computed(() => {
  const rows: {
    step: number
    catKey: string
    value: string
    sub: string
  }[] = []
  rows.push({
    step: 0,
    catKey: 'wizard.catProjectInfo',
    value: wizard.draftName || '—',
    sub: `${t('wizard.projectSlug').toLowerCase()}: ${wizard.draftSlug || '—'}`,
  })
  if (wizard.assets.bom) {
    rows.push({
      step: 1,
      catKey: 'wizard.catBomList',
      value: assetName('bom') ?? '—',
      sub: t('wizard.bomItemsLine', { items: wizard.bomItems.length, mi: miCount.value }),
    })
  }
  for (const [kind, catKey] of [
    ['golden_top', 'wizard.catGoldenTop'],
    ['golden_bottom', 'wizard.catGoldenBottom'],
    ['drawing', 'wizard.catDrawing'],
  ] as const) {
    const a = wizard.assets[kind]
    if (!a) continue
    const dims = dimLabel(kind)
    const parts = [formatBytes(a.size_bytes), dims].filter(Boolean)
    rows.push({
      step: kind === 'drawing' ? 3 : 2,
      catKey,
      value: assetName(kind) ?? '—',
      sub: parts.join(' · '),
    })
  }
  return rows
})

const whatNext = [1, 2, 3, 4].map((n) => ({
  n,
  titleKey: `wizard.next${n}Title`,
  bodyKey: `wizard.next${n}Body`,
}))
</script>

<template>
  <div class="p-8 max-w-[1200px] mx-auto">
    <!-- Stepper -->
    <ol data-testid="wizard-stepper" class="flex items-center gap-2 mb-8">
      <li
        v-for="(step, idx) in STEPS"
        :key="step.key"
        :data-testid="`wizard-step-${idx + 1}`"
        class="flex items-center gap-2"
        :class="idx < STEPS.length - 1 ? 'flex-1' : ''"
      >
        <div class="flex flex-col items-center gap-1.5 shrink-0">
          <span
            class="h-9 w-9 grid place-items-center rounded-full text-sm font-mono font-semibold transition"
            :class="
              idx < stepIndex
                ? 'bg-primary-500 text-white'
                : idx === stepIndex
                  ? 'bg-primary-500 text-white ring-4 ring-primary-100'
                  : 'bg-ink-100 text-ink-400'
            "
          >
            <template v-if="idx < stepIndex">✓</template>
            <template v-else>{{ idx + 1 }}</template>
          </span>
          <span
            class="text-xs whitespace-nowrap"
            :class="idx === stepIndex ? 'font-semibold text-ink-900' : 'font-medium text-ink-400'"
          >
            {{ t(step.stepKey) }}
          </span>
        </div>
        <span
          v-if="idx < STEPS.length - 1"
          class="flex-1 h-0.5 mb-5 rounded-full"
          :class="idx < stepIndex ? 'bg-primary-400' : 'bg-ink-200'"
        />
      </li>
    </ol>

    <!-- Panel heading -->
    <header class="mb-6">
      <h1 class="text-2xl font-semibold text-ink-900">{{ t(current.titleKey) }}</h1>
      <p class="mt-1 text-sm text-ink-500 max-w-3xl">{{ t(current.blurbKey) }}</p>
      <span
        v-if="current.key === 'drawing'"
        class="mt-2 inline-flex items-center h-6 px-2.5 rounded-full bg-red-50 border border-red-200 text-[11px] font-semibold text-red-700"
      >
        {{ t('wizard.drawingRequiredBadge') }}
      </span>
    </header>

    <p
      v-if="wizard.error"
      data-testid="wizard-error"
      role="alert"
      class="mb-5 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700"
    >
      {{ wizard.error }}
    </p>

    <!-- ───────── Step 1: Project information ───────── -->
    <div
      v-if="current.key === 'project'"
      data-testid="wizard-panel"
      class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start"
    >
      <div class="rounded-xl bg-white border border-border-default shadow-card p-6 space-y-5">
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
          {{ t('wizard.projectDetails') }}
        </p>
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.projectName') }}</span>
          <input
            v-model="wizard.draftName"
            data-testid="wizard-name-input"
            type="text"
            placeholder="Mainboard XR-200"
            :disabled="wizard.project != null"
            class="w-full h-11 px-3 rounded-lg border border-border-default bg-white focus:border-primary-500 focus:ring-2 focus:ring-primary-100 outline-none transition disabled:bg-surface-raised disabled:text-ink-500"
            @blur="wizard.autofillSlug()"
          />
          <span class="text-xs text-ink-500">{{ t('wizard.nameHelp') }}</span>
        </label>
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.projectSlug') }}</span>
          <div class="relative">
            <input
              v-model="wizard.draftSlug"
              data-testid="wizard-slug-input"
              type="text"
              placeholder="mainboard-xr-200"
              pattern="[a-z0-9-]+"
              :disabled="wizard.project != null"
              class="w-full h-11 pl-3 pr-16 rounded-lg border border-border-default bg-surface-raised font-mono focus:border-primary-500 focus:ring-2 focus:ring-primary-100 outline-none transition disabled:text-ink-500"
            />
            <span
              class="absolute right-3 top-1/2 -translate-y-1/2 text-[11px] font-mono text-ink-400"
            >
              auto
            </span>
          </div>
          <span class="text-xs text-ink-500">{{ t('wizard.slugHint') }}</span>
        </label>
      </div>

      <!-- Setup checklist -->
      <aside
        data-testid="wizard-checklist"
        class="rounded-xl bg-primary-50/60 border border-primary-200 p-5 space-y-3.5"
      >
        <p class="text-[11px] font-mono uppercase tracking-wider text-primary-800">
          {{ t('wizard.setupChecklist') }}
        </p>
        <ul class="space-y-3">
          <li v-for="(step, idx) in STEPS" :key="step.key" class="flex items-start gap-2.5">
            <span
              class="h-5 w-5 shrink-0 grid place-items-center rounded-full text-[10px] mt-0.5 transition"
              :class="
                idx < stepIndex || (idx === 0 && wizard.project)
                  ? 'bg-primary-600 text-white'
                  : idx === stepIndex
                    ? 'border-2 border-primary-400 text-transparent'
                    : 'border border-ink-300 text-transparent'
              "
            >
              ✓
            </span>
            <span
              class="text-[13px] leading-snug"
              :class="idx === stepIndex ? 'text-ink-900 font-medium' : 'text-ink-600'"
            >
              {{ t(`wizard.chk${idx + 1}`) }}
            </span>
          </li>
        </ul>
      </aside>
    </div>

    <!-- ───────── Step 2: BOM upload ───────── -->
    <div
      v-else-if="current.key === 'bom'"
      data-testid="wizard-panel"
      class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start"
    >
      <div class="space-y-5 min-w-0">
        <label
          data-testid="wizard-bom-dropzone"
          class="flex flex-col items-center justify-center text-center min-h-44 rounded-xl px-6 py-8 cursor-pointer transition"
          :class="[
            wizard.assets.bom
              ? 'bg-primary-50 border-2 border-dashed border-primary-400'
              : 'bg-surface-raised border-2 border-dashed border-ink-300 hover:border-primary-400',
            wizard.busy ? 'opacity-60 pointer-events-none' : '',
          ]"
        >
          <span
            class="h-14 w-14 grid place-items-center rounded-xl mb-3"
            :class="wizard.assets.bom ? 'bg-primary-600 text-white' : 'bg-ink-100 text-ink-400'"
          >
            <span class="block h-5 w-7 rounded-sm border-2 border-current" />
          </span>
          <template v-if="wizard.assets.bom">
            <span class="text-base font-semibold text-ink-900 font-mono">
              {{ assetName('bom') }}
              <span v-if="wizard.assets.bom.size_bytes" class="text-ink-500">
                · {{ formatBytes(wizard.assets.bom.size_bytes) }}
              </span>
            </span>
            <span class="mt-1 text-sm text-primary-700">{{ t('wizard.bomDropParsed') }}</span>
          </template>
          <template v-else>
            <span class="text-sm font-medium text-ink-700">{{ t('wizard.uploadBom') }}</span>
            <span class="mt-1 text-xs text-ink-500">.xlsx / .csv · SAP ZLMM_BOM_REPORT</span>
          </template>
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            class="hidden"
            @change="onFile('bom', $event)"
          />
        </label>

        <div
          v-if="wizard.assets.bom && wizard.bomItems.length === 0"
          class="text-xs text-ink-500"
        >
          {{ t('wizard.bomUploadedAwaitingParse') }}
          <button
            type="button"
            class="ml-2 font-mono text-primary-700 hover:underline"
            @click="wizard.fetchBomItems()"
          >
            {{ t('common.refresh') }}
          </button>
        </div>

        <div
          v-if="wizard.bomItems.length > 0"
          data-testid="wizard-bom-table"
          class="rounded-xl border border-border-default overflow-hidden"
        >
          <div class="max-h-80 overflow-y-auto">
            <table class="w-full text-sm">
              <thead
                class="bg-surface-raised text-[11px] font-mono uppercase text-ink-500 sticky top-0"
              >
                <tr class="border-b border-border-default">
                  <th class="text-left px-4 py-2.5 font-medium">{{ t('wizard.colDesignator') }}</th>
                  <th class="text-left px-4 py-2.5 font-medium">{{ t('wizard.colDescription') }}</th>
                  <th class="text-right px-4 py-2.5 font-medium">{{ t('wizard.colQty') }}</th>
                  <th class="text-left px-4 py-2.5 font-medium">{{ t('wizard.colType') }}</th>
                  <th class="text-left px-4 py-2.5 font-medium">{{ t('wizard.colMiq') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in wizard.bomItems.slice(0, 50)"
                  :key="item.id"
                  class="border-t border-border-subtle"
                >
                  <td class="px-4 py-2.5 font-mono whitespace-nowrap">{{ item.designator }}</td>
                  <td class="px-4 py-2.5 text-ink-700 truncate max-w-[280px]">
                    {{ item.value ?? '—' }}
                  </td>
                  <td class="px-4 py-2.5 text-right font-mono tabular-nums">{{ item.qty ?? '—' }}</td>
                  <td class="px-4 py-2.5 font-mono text-ink-600">{{ item.component_type ?? '—' }}</td>
                  <td class="px-4 py-2.5">
                    <span
                      v-if="item.mi_likely"
                      class="inline-flex items-center h-5 px-2 rounded-full bg-amber-50 border border-amber-200 text-[11px] font-medium text-amber-800"
                    >
                      MI
                    </span>
                    <span v-else class="text-xs text-ink-400">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p
            v-if="wizard.bomItems.length > 50"
            class="px-4 py-2 text-xs text-ink-500 bg-surface-raised border-t border-border-default"
          >
            {{ t('wizard.bomTruncated', { shown: 50, total: wizard.bomItems.length }) }}
          </p>
        </div>
      </div>

      <!-- Parse summary + MI heuristic note -->
      <aside class="space-y-4">
        <div
          data-testid="wizard-parse-summary"
          class="rounded-xl bg-white border border-border-default shadow-card p-5"
        >
          <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500 mb-3">
            {{ t('wizard.parseSummary') }}
          </p>
          <dl class="space-y-2.5 text-sm">
            <div class="flex items-center justify-between">
              <dt class="text-ink-600">{{ t('wizard.bomItemsDetected') }}</dt>
              <dd class="font-semibold font-mono tabular-nums text-ink-900">
                {{ wizard.bomItems.length }}
              </dd>
            </div>
            <div class="flex items-center justify-between">
              <dt class="text-ink-600">{{ t('wizard.miLikelyCount') }}</dt>
              <dd class="font-semibold font-mono tabular-nums text-primary-700">{{ miCount }}</dd>
            </div>
          </dl>
        </div>

        <div
          v-if="wizard.bomItems.length > 0"
          class="rounded-xl bg-blue-50 border border-blue-200 p-4"
        >
          <p
            class="flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-blue-700"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-blue-500" />
            {{ t('wizard.miNoteTitle') }}
          </p>
          <p class="mt-2 text-[13px] text-blue-900/80 leading-snug">
            {{ t('wizard.miNoteBody', { n: miCount }) }}
          </p>
        </div>
      </aside>
    </div>

    <!-- ───────── Step 3: Golden samples ───────── -->
    <div
      v-else-if="current.key === 'golden'"
      data-testid="wizard-panel"
      class="space-y-5"
    >
      <div class="grid grid-cols-1 lg:grid-cols-[1fr_1fr_300px] gap-4">
        <label
          v-for="side in [
            { kind: 'golden_top' as AssetKind, tid: 'wizard-golden-top', dropKey: 'wizard.goldenDropTop', tag: 'TOP' },
            { kind: 'golden_bottom' as AssetKind, tid: 'wizard-golden-bottom', dropKey: 'wizard.goldenDropBottom', tag: 'BOTTOM' },
          ]"
          :key="side.kind"
          :data-testid="side.tid"
          class="group relative flex flex-col rounded-xl p-4 cursor-pointer transition min-h-[300px]"
          :class="[
            wizard.assets[side.kind]
              ? 'bg-primary-50 border-2 border-primary-500'
              : 'bg-white border-2 border-dashed border-ink-300 hover:border-primary-400',
            wizard.busy ? 'opacity-60 pointer-events-none' : '',
          ]"
        >
          <template v-if="wizard.assets[side.kind]">
            <div
              class="flex-1 rounded-lg overflow-hidden bg-ink-900 grid place-items-center min-h-[150px] relative"
            >
              <img
                v-if="previewUrls[side.kind]"
                :src="previewUrls[side.kind]"
                :alt="side.tag"
                class="h-full w-full object-cover"
              />
              <span
                v-else
                class="text-[10px] font-mono uppercase tracking-wider text-ink-300"
              >
                {{ side.tag }}
              </span>
              <span
                class="absolute bottom-2 right-2 text-[10px] font-mono uppercase tracking-wider text-primary-300/80"
              >
                {{ side.tag }}
              </span>
            </div>
            <div class="mt-3 flex flex-col items-center text-center">
              <span class="h-6 w-6 grid place-items-center rounded-full bg-primary-600 text-white text-xs">✓</span>
              <span class="mt-1.5 text-sm font-medium text-ink-900 font-mono truncate max-w-full">
                {{ assetName(side.kind) }}
                <span v-if="wizard.assets[side.kind]?.size_bytes" class="text-ink-500">
                  · {{ formatBytes(wizard.assets[side.kind]!.size_bytes) }}
                </span>
              </span>
              <span class="text-xs text-primary-700 mt-0.5">
                {{ t('wizard.uploadedLabel') }}<template v-if="dimLabel(side.kind)"> · {{ dimLabel(side.kind) }}</template>
              </span>
              <span
                v-if="wizard.assets[side.kind]?.qc"
                :data-testid="`wizard-qc-${side.kind}`"
                class="mt-1.5 inline-flex items-center gap-1 h-5 px-2 rounded-full text-[11px] font-medium"
                :class="qcTone(wizard.assets[side.kind]!.qc!.verdict)"
                :title="qcTitle(wizard.assets[side.kind]!.qc!)"
              >
                {{ t(`wizard.qc.${wizard.assets[side.kind]!.qc!.verdict}`) }}
              </span>
              <span class="mt-2 text-[11px] text-ink-500 opacity-0 group-hover:opacity-100 transition">
                {{ t('wizard.replaceImage') }}
              </span>
            </div>
          </template>

          <template v-else>
            <div class="flex-1 grid place-items-center">
              <div class="flex flex-col items-center text-center">
                <span class="h-12 w-12 grid place-items-center rounded-full bg-ink-100 text-ink-500 text-xl mb-3">↑</span>
                <span class="text-sm font-medium text-ink-700">{{ t(side.dropKey) }}</span>
                <span class="mt-1 text-xs text-ink-500 max-w-[200px]">
                  {{ t('wizard.goldenFileHint') }}
                </span>
              </div>
            </div>
          </template>

          <input type="file" accept="image/*" class="hidden" @change="onFile(side.kind, $event)" />
        </label>

        <aside
          data-testid="wizard-photo-tips"
          class="rounded-xl border border-border-default bg-white px-4 py-4 space-y-3 self-start"
        >
          <h3 class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
            {{ t('wizard.photoTipsTitle') }}
          </h3>
          <ol class="space-y-3">
            <li v-for="n in [1, 2, 3, 4]" :key="n" class="flex items-start gap-2.5">
              <span
                class="h-5 w-5 shrink-0 grid place-items-center rounded-full border border-ink-300 text-[10px] font-mono text-ink-600"
              >
                {{ n }}
              </span>
              <div class="flex-1 min-w-0">
                <p class="text-[13px] font-medium text-ink-900 leading-tight">
                  {{ t(`wizard.photoTip${n}Title`) }}
                </p>
                <p class="mt-0.5 text-xs text-ink-500 leading-snug">
                  {{ t(`wizard.photoTip${n}Body`) }}
                </p>
              </div>
            </li>
          </ol>
        </aside>
      </div>

      <!-- Both uploaded -->
      <div
        v-if="wizard.assets.golden_top && wizard.assets.golden_bottom"
        class="flex items-start gap-3 rounded-xl bg-primary-50 border border-primary-200 px-4 py-3 max-w-3xl"
      >
        <span class="h-6 w-6 grid place-items-center rounded-full bg-primary-600 text-white text-xs mt-0.5">✓</span>
        <div>
          <p class="text-sm font-semibold text-primary-900">{{ t('wizard.goldenBothTitle') }}</p>
          <p class="mt-0.5 text-xs text-primary-900/70 leading-snug">{{ t('wizard.goldenBothDetail') }}</p>
        </div>
      </div>

      <!-- Bottom missing warning -->
      <div
        v-else-if="wizard.assets.golden_top && !bottomSkipped"
        class="flex items-start gap-3 rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 max-w-3xl"
      >
        <span class="text-lg leading-none mt-0.5">⚠</span>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold text-amber-900">{{ t('wizard.goldenBottomMissingTitle') }}</p>
          <p class="mt-0.5 text-xs text-amber-800 leading-snug">{{ t('wizard.goldenBottomMissingDetail') }}</p>
        </div>
        <button
          type="button"
          class="shrink-0 h-9 px-3 rounded-lg bg-white border border-amber-300 text-sm font-medium text-amber-900 hover:bg-amber-100 transition"
          @click="bottomSkipped = true"
        >
          {{ t('wizard.goldenSkipBottom') }}
        </button>
      </div>

      <div
        v-else-if="wizard.assets.golden_top && bottomSkipped"
        class="flex items-center gap-3 rounded-xl bg-surface-raised border border-border-default px-4 py-2.5 text-xs text-ink-600 max-w-3xl"
      >
        <span>{{ t('wizard.goldenBottomOptional') }}</span>
        <button
          type="button"
          class="ml-auto font-medium text-primary-700 hover:underline"
          @click="bottomSkipped = false"
        >
          {{ t('wizard.goldenSkipUndo') }}
        </button>
      </div>
    </div>

    <!-- ───────── Step 4: PCB drawing ───────── -->
    <div
      v-else-if="current.key === 'drawing'"
      data-testid="wizard-panel"
      class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start"
    >
      <div class="space-y-4 min-w-0">
        <label
          data-testid="wizard-drawing-dropzone"
          class="flex flex-col items-center justify-center text-center rounded-xl px-6 py-10 cursor-pointer transition"
          :class="[
            wizard.assets.drawing
              ? 'bg-primary-50 border-2 border-primary-500 min-h-[220px]'
              : 'bg-white border-2 border-dashed border-ink-300 hover:border-primary-400 min-h-[260px]',
            wizard.busy ? 'opacity-60 pointer-events-none' : '',
          ]"
        >
          <template v-if="wizard.assets.drawing">
            <div
              class="w-full rounded-lg overflow-hidden bg-white border border-primary-200 grid place-items-center min-h-[160px] mb-3"
            >
              <img
                v-if="previewUrls.drawing"
                :src="previewUrls.drawing"
                alt="drawing"
                class="max-h-44 w-full object-contain"
              />
              <div v-else class="relative w-full aspect-[2/1] bg-surface-raised">
                <span
                  v-for="part in EXAMPLE_PARTS"
                  :key="part.id"
                  class="absolute border border-primary-400 rounded-sm bg-primary-50/40 text-[8px] font-mono text-primary-700 px-0.5"
                  :style="{ left: part.x + '%', top: part.y + '%', width: part.w + '%', height: part.h + '%' }"
                >
                  {{ part.id }}
                </span>
              </div>
            </div>
            <span class="text-sm font-semibold text-ink-900 font-mono">
              {{ assetName('drawing') }}
              <span v-if="wizard.assets.drawing.size_bytes" class="text-ink-500">
                · {{ formatBytes(wizard.assets.drawing.size_bytes) }}
              </span>
            </span>
            <span class="text-xs text-primary-700 mt-0.5">
              {{ t('wizard.uploadedLabel') }}<template v-if="dimLabel('drawing')"> · {{ dimLabel('drawing') }}</template>
            </span>
          </template>
          <template v-else>
            <span class="h-12 w-12 grid place-items-center rounded-full bg-ink-100 text-ink-500 text-xl mb-3">↑</span>
            <span class="text-sm font-medium text-ink-700">{{ t('wizard.drawingDropTitle') }}</span>
            <span class="mt-1 text-xs text-ink-500">{{ t('wizard.drawingDropHint') }}</span>
          </template>
          <input type="file" accept="image/*" class="hidden" @change="onFile('drawing', $event)" />
        </label>

        <div
          v-if="wizard.assets.drawing"
          class="rounded-xl bg-primary-50 border border-primary-200 px-4 py-3"
        >
          <p class="text-sm font-semibold text-primary-900">{{ t('wizard.drawingSavedTitle') }}</p>
          <p class="mt-0.5 text-xs text-primary-900/70 leading-snug">{{ t('wizard.drawingSavedBody') }}</p>
        </div>
      </div>

      <!-- Example card -->
      <aside
        data-testid="wizard-drawing-example"
        class="rounded-xl border border-border-default bg-white p-5 space-y-3"
      >
        <p class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
          {{ t('wizard.drawingExample') }}
        </p>
        <div class="relative w-full aspect-[2/1] rounded-lg bg-surface-raised border border-border-subtle overflow-hidden">
          <span
            v-for="part in EXAMPLE_PARTS"
            :key="part.id"
            class="absolute border border-ink-400 rounded-sm bg-white/70 text-[8px] font-mono text-ink-600 leading-none px-0.5 pt-0.5"
            :style="{ left: part.x + '%', top: part.y + '%', width: part.w + '%', height: part.h + '%' }"
          >
            {{ part.id }}
          </span>
        </div>
        <div>
          <p class="text-sm font-medium text-ink-900">{{ t('wizard.drawingHelpsTitle') }}</p>
          <ul class="mt-2 space-y-1 text-xs text-ink-600">
            <li>· {{ t('wizard.drawingHelp1') }}</li>
            <li>· {{ t('wizard.drawingHelp2') }}</li>
            <li>· {{ t('wizard.drawingHelp3') }}</li>
          </ul>
        </div>
      </aside>
    </div>

    <!-- ───────── Step 5: Review and create ───────── -->
    <div
      v-else
      data-testid="wizard-panel"
      class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start"
    >
      <div data-testid="wizard-review" class="space-y-3">
        <div
          v-for="row in reviewRows"
          :key="row.catKey"
          data-testid="wizard-review-row"
          class="flex items-center gap-4 rounded-xl bg-white border border-border-default shadow-card px-5 py-4"
        >
          <span class="h-7 w-7 shrink-0 grid place-items-center rounded-full bg-primary-100 text-primary-700 text-xs">✓</span>
          <div class="flex-1 min-w-0">
            <p class="text-xs font-mono uppercase tracking-wider text-ink-400">{{ t(row.catKey) }}</p>
            <p class="text-sm font-semibold text-ink-900 truncate">{{ row.value }}</p>
            <p class="text-xs text-ink-500 truncate">{{ row.sub }}</p>
          </div>
          <button
            type="button"
            :data-testid="`wizard-edit-${row.step}`"
            class="shrink-0 h-8 px-3 rounded-md border border-border-default text-xs font-medium text-ink-700 hover:bg-ink-50 transition"
            @click="goToStep(row.step)"
          >
            {{ t('wizard.reviewEdit') }}
          </button>
        </div>
      </div>

      <!-- What happens next -->
      <aside data-testid="wizard-what-next" class="rounded-xl bg-ink-900 p-5 space-y-4">
        <p class="text-[11px] font-mono uppercase tracking-wider text-primary-400">
          {{ t('wizard.whatNextTitle') }}
        </p>
        <ol class="space-y-4">
          <li v-for="item in whatNext" :key="item.n" class="flex items-start gap-3">
            <span class="h-6 w-6 shrink-0 grid place-items-center rounded-full bg-primary-600 text-white text-xs font-mono">
              {{ item.n }}
            </span>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-white">{{ t(item.titleKey) }}</p>
              <p class="mt-0.5 text-xs text-ink-400 leading-snug">{{ t(item.bodyKey) }}</p>
            </div>
          </li>
        </ol>
      </aside>
    </div>

    <!-- Footer -->
    <footer class="mt-8 flex items-center justify-between">
      <AppButton
        data-testid="wizard-cancel"
        variant="ghost"
        :disabled="wizard.busy"
        @click="router.push({ name: 'dashboard' })"
      >
        {{ t('wizard.cancel') }}
      </AppButton>
      <div class="flex items-center gap-3">
        <AppButton
          data-testid="wizard-back"
          variant="secondary"
          :disabled="wizard.isFirst || wizard.busy"
          @click="wizard.back()"
        >
          ← {{ t('common.back') }}
        </AppButton>
        <AppButton
          v-if="!wizard.isLast"
          data-testid="wizard-continue"
          :disabled="!wizard.canAdvance || wizard.busy"
          @click="handleNext"
        >
          {{ wizard.busy ? t('common.loading') : t('common.continue') }} →
        </AppButton>
        <AppButton v-else data-testid="wizard-create" :disabled="!wizard.projectId" @click="handleFinish">
          {{ t('wizard.createProject') }} →
        </AppButton>
      </div>
    </footer>
  </div>
</template>
