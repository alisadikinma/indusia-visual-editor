<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useWizardStore } from '@/stores/wizard'
import { useProjectsStore } from '@/stores/projects'
import type { AssetKind } from '@/api/assets'

interface StepDef {
  key: 'project' | 'bom' | 'golden' | 'drawing' | 'review'
  titleKey: string
  blurbKey: string
}

const STEPS: StepDef[] = [
  { key: 'project', titleKey: 'wizard.s1Title', blurbKey: 'wizard.s1Blurb' },
  { key: 'bom', titleKey: 'wizard.s2Title', blurbKey: 'wizard.s2Blurb' },
  { key: 'golden', titleKey: 'wizard.s3Title', blurbKey: 'wizard.s3Blurb' },
  { key: 'drawing', titleKey: 'wizard.s4Title', blurbKey: 'wizard.s4Blurb' },
  { key: 'review', titleKey: 'wizard.s5Title', blurbKey: 'wizard.s5Blurb' },
]

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const wizard = useWizardStore()
const projects = useProjectsStore()

const stepIndex = computed(() => wizard.stepIndex)
const current = computed(() => STEPS[stepIndex.value])

const idParam = computed(() => String(route.params.id ?? ''))

onMounted(async () => {
  // /projects/new/wizard → fresh start
  if (idParam.value === 'new' || idParam.value === '') {
    wizard.reset()
    return
  }
  // Hydrate from existing project
  if (wizard.project?.id !== idParam.value) {
    wizard.reset()
    if (!projects.items.length) await projects.fetchAll()
    const existing = projects.items.find((p) => p.id === idParam.value)
    if (existing) wizard.hydrateFromExisting(existing)
  }
})

// After project creation, rewrite URL to include real id
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

async function onFile(kind: AssetKind, e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!wizard.project) {
    wizard.error = t('wizard.errMissingProject')
    return
  }
  try {
    await wizard.uploadAsset(kind, file)
  } catch {
    /* error displayed inline */
  } finally {
    input.value = ''
  }
}

const assetName = (kind: AssetKind): string | null => {
  const a = wizard.assets[kind]
  if (!a) return null
  return a.path.split('/').pop() ?? a.path
}
</script>

<template>
  <div class="p-8 max-w-[1100px] mx-auto">
    <header class="mb-8">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('wizard.kicker') }}
      </p>
      <h1 class="mt-1 text-2xl font-semibold text-ink-900">{{ t('wizard.title') }}</h1>

      <ol class="mt-6 flex items-center gap-2">
        <li
          v-for="(step, idx) in STEPS"
          :key="step.key"
          class="flex-1 flex items-center gap-2"
        >
          <div class="flex items-center gap-2 min-w-0">
            <span
              class="h-7 w-7 grid place-items-center rounded-full text-xs font-mono font-semibold shrink-0 transition"
              :class="
                idx < stepIndex
                  ? 'bg-primary-700 text-white'
                  : idx === stepIndex
                    ? 'bg-primary-50 text-primary-800 border border-primary-200'
                    : 'bg-ink-100 text-ink-500'
              "
            >
              {{ idx < stepIndex ? '✓' : String(idx + 1).padStart(2, '0') }}
            </span>
            <span
              class="text-xs font-medium hidden md:inline truncate"
              :class="idx === stepIndex ? 'text-ink-900' : 'text-ink-500'"
            >
              {{ t(step.titleKey) }}
            </span>
          </div>
          <span
            v-if="idx < STEPS.length - 1"
            class="flex-1 h-px"
            :class="idx < stepIndex ? 'bg-primary-300' : 'bg-ink-200'"
          />
        </li>
      </ol>
    </header>

    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-8 space-y-6">
      <div>
        <h2 class="text-lg font-semibold text-ink-900">{{ t(current.titleKey) }}</h2>
        <p class="mt-1 text-sm text-ink-500">{{ t(current.blurbKey) }}</p>
      </div>

      <p
        v-if="wizard.error"
        role="alert"
        class="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700"
      >
        {{ wizard.error }}
      </p>

      <!-- Step 1: project basics -->
      <div v-if="current.key === 'project'" class="space-y-4 max-w-lg">
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.projectName') }}</span>
          <input
            v-model="wizard.draftName"
            type="text"
            placeholder="PCB Inspection v1"
            :disabled="wizard.project != null"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition disabled:bg-ink-50 disabled:text-ink-500"
            @blur="wizard.autofillSlug()"
          />
        </label>
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.projectSlug') }}</span>
          <input
            v-model="wizard.draftSlug"
            type="text"
            placeholder="pcb-inspection-v1"
            pattern="[a-z0-9-]+"
            :disabled="wizard.project != null"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white font-mono focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition disabled:bg-ink-50 disabled:text-ink-500"
          />
          <span class="text-xs text-ink-500">{{ t('wizard.slugHint') }}</span>
        </label>
        <p
          v-if="wizard.project"
          class="text-xs text-primary-900 bg-primary-50 border border-primary-200 rounded-md px-3 py-2"
        >
          {{ t('wizard.projectCreated') }}
          <span class="font-mono ml-1">{{ wizard.project.id }}</span>
        </p>
      </div>

      <!-- Step 2: BOM upload + preview -->
      <div v-else-if="current.key === 'bom'" class="space-y-4">
        <label
          class="flex flex-col items-center justify-center min-h-32 border-2 border-dashed border-ink-300 rounded-xl bg-ink-50 px-6 py-8 cursor-pointer hover:border-primary-400 transition"
          :class="wizard.busy ? 'opacity-60 pointer-events-none' : ''"
        >
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.uploadBom') }}</span>
          <span class="mt-1 text-xs text-ink-500">.xlsx / .csv · SAP ZLMM_BOM_REPORT OK</span>
          <span v-if="assetName('bom')" class="mt-3 text-xs font-mono text-primary-700">
            ✓ {{ assetName('bom') }}
          </span>
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
          class="rounded-lg border border-ink-200 overflow-hidden"
        >
          <header class="flex items-center justify-between px-4 py-2.5 bg-ink-50 border-b border-ink-200">
            <h3 class="text-sm font-semibold text-ink-900">
              {{ t('wizard.bomPreviewTitle', { n: wizard.bomItems.length }) }}
            </h3>
            <span class="text-xs font-mono text-ink-500">
              {{ wizard.bomItems.filter((i) => i.mi_likely).length }} MI ·
              {{ wizard.bomItems.length - wizard.bomItems.filter((i) => i.mi_likely).length }} SMT
            </span>
          </header>
          <div class="max-h-72 overflow-y-auto">
            <table class="w-full text-sm">
              <thead class="bg-white text-xs font-mono uppercase text-ink-500 sticky top-0">
                <tr class="border-b border-ink-100">
                  <th class="text-left px-4 py-2 font-medium">{{ t('wizard.colDesignator') }}</th>
                  <th class="text-left px-4 py-2 font-medium">{{ t('wizard.colValue') }}</th>
                  <th class="text-left px-4 py-2 font-medium">{{ t('wizard.colPackage') }}</th>
                  <th class="text-right px-4 py-2 font-medium">{{ t('wizard.colQty') }}</th>
                  <th class="text-left px-4 py-2 font-medium">{{ t('wizard.colMi') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in wizard.bomItems.slice(0, 50)"
                  :key="item.id"
                  class="border-t border-ink-100"
                >
                  <td class="px-4 py-2 font-mono">{{ item.designator }}</td>
                  <td class="px-4 py-2">{{ item.value ?? '—' }}</td>
                  <td class="px-4 py-2 font-mono text-ink-600">{{ item.package ?? '—' }}</td>
                  <td class="px-4 py-2 text-right font-mono tabular-nums">{{ item.qty ?? '—' }}</td>
                  <td class="px-4 py-2">
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
            class="px-4 py-2 text-xs text-ink-500 bg-ink-50 border-t border-ink-200"
          >
            {{ t('wizard.bomTruncated', { shown: 50, total: wizard.bomItems.length }) }}
          </p>
        </div>
      </div>

      <!-- Step 3: golden samples -->
      <div v-else-if="current.key === 'golden'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label
          v-for="side in [
            { kind: 'golden_top' as AssetKind, labelKey: 'wizard.goldenTop' },
            { kind: 'golden_bottom' as AssetKind, labelKey: 'wizard.goldenBottom' },
          ]"
          :key="side.kind"
          class="flex flex-col items-center justify-center min-h-40 border-2 border-dashed border-ink-300 rounded-xl bg-ink-50 px-6 py-8 cursor-pointer hover:border-primary-400 transition"
          :class="wizard.busy ? 'opacity-60 pointer-events-none' : ''"
        >
          <span class="text-sm font-medium text-ink-700">{{ t(side.labelKey) }}</span>
          <span class="mt-1 text-xs text-ink-500">.jpg / .png · ≥1920px</span>
          <span v-if="assetName(side.kind)" class="mt-3 text-xs font-mono text-primary-700">
            ✓ {{ assetName(side.kind) }}
          </span>
          <input
            type="file"
            accept="image/*"
            class="hidden"
            @change="onFile(side.kind, $event)"
          />
        </label>
      </div>

      <!-- Step 4: drawing -->
      <div v-else-if="current.key === 'drawing'" class="max-w-lg space-y-3">
        <label
          class="flex flex-col items-center justify-center min-h-40 border-2 border-dashed border-ink-300 rounded-xl bg-ink-50 px-6 py-8 cursor-pointer hover:border-primary-400 transition"
          :class="wizard.busy ? 'opacity-60 pointer-events-none' : ''"
        >
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.uploadDrawing') }}</span>
          <span class="mt-1 text-xs text-ink-500">{{ t('wizard.drawingNote') }}</span>
          <span v-if="assetName('drawing')" class="mt-3 text-xs font-mono text-primary-700">
            ✓ {{ assetName('drawing') }}
          </span>
          <input
            type="file"
            accept="image/*"
            class="hidden"
            @change="onFile('drawing', $event)"
          />
        </label>
        <p
          class="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2"
        >
          {{ t('wizard.drawingRequired') }}
        </p>
      </div>

      <!-- Step 5: review -->
      <div v-else class="space-y-4">
        <dl class="grid grid-cols-1 md:grid-cols-2 gap-y-3 gap-x-6 text-sm">
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.projectName') }}</dt>
            <dd class="font-medium text-ink-900">{{ wizard.draftName || '—' }}</dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.projectSlug') }}</dt>
            <dd class="font-mono text-ink-900">{{ wizard.draftSlug || '—' }}</dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">BOM</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">
              {{ assetName('bom') ?? '—' }}
            </dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.bomRowCount') }}</dt>
            <dd class="font-mono tabular-nums text-ink-900">{{ wizard.bomItems.length }}</dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.goldenTop') }}</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">
              {{ assetName('golden_top') ?? '—' }}
            </dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.goldenBottom') }}</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">
              {{ assetName('golden_bottom') ?? '—' }}
            </dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.drawingShort') }}</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">
              {{ assetName('drawing') ?? '—' }}
            </dd>
          </div>
        </dl>
        <p
          class="text-xs text-primary-900 bg-primary-50 border border-primary-200 rounded-md px-3 py-2"
        >
          {{ t('wizard.reviewNote') }}
        </p>
      </div>
    </section>

    <footer class="mt-6 flex items-center justify-between">
      <AppButton variant="ghost" :disabled="wizard.isFirst || wizard.busy" @click="wizard.back()">
        ← {{ t('common.back') }}
      </AppButton>
      <div class="flex items-center gap-3">
        <span class="text-xs font-mono text-ink-500">
          {{ stepIndex + 1 }} / {{ STEPS.length }}
        </span>
        <AppButton
          v-if="!wizard.isLast"
          :disabled="!wizard.canAdvance || wizard.busy"
          @click="handleNext"
        >
          {{ wizard.busy ? t('common.loading') : t('common.continue') }} →
        </AppButton>
        <AppButton v-else :disabled="!wizard.projectId" @click="handleFinish">
          {{ t('wizard.finish') }} →
        </AppButton>
      </div>
    </footer>
  </div>
</template>
