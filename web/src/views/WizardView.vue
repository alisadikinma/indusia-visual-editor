<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

interface Step {
  key: string
  titleKey: string
  blurbKey: string
}

const steps: Step[] = [
  { key: 'project', titleKey: 'wizard.s1Title', blurbKey: 'wizard.s1Blurb' },
  { key: 'bom', titleKey: 'wizard.s2Title', blurbKey: 'wizard.s2Blurb' },
  { key: 'golden', titleKey: 'wizard.s3Title', blurbKey: 'wizard.s3Blurb' },
  { key: 'drawing', titleKey: 'wizard.s4Title', blurbKey: 'wizard.s4Blurb' },
  { key: 'review', titleKey: 'wizard.s5Title', blurbKey: 'wizard.s5Blurb' },
]

const currentIndex = ref(0)
const current = computed(() => steps[currentIndex.value])
const isFirst = computed(() => currentIndex.value === 0)
const isLast = computed(() => currentIndex.value === steps.length - 1)

const form = ref({
  name: '',
  slug: '',
  bomFileName: '',
  goldenTopName: '',
  goldenBottomName: '',
  drawingName: '',
})

function back() {
  if (!isFirst.value) currentIndex.value--
}

function next() {
  if (!isLast.value) currentIndex.value++
}

function finish() {
  router.push({ name: 'labeling', params: { id: route.params.id ?? 'new' } })
}

function onFile(field: keyof typeof form.value, e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) form.value[field] = file.name
}
</script>

<template>
  <div class="p-8 max-w-[1100px] mx-auto">
    <!-- Stepper -->
    <header class="mb-8">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('wizard.kicker') }}
      </p>
      <h1 class="mt-1 text-2xl font-semibold text-ink-900">{{ t('wizard.title') }}</h1>

      <ol class="mt-6 flex items-center gap-2">
        <li
          v-for="(step, idx) in steps"
          :key="step.key"
          class="flex-1 flex items-center gap-2"
        >
          <div class="flex items-center gap-2 min-w-0">
            <span
              class="h-7 w-7 grid place-items-center rounded-full text-xs font-mono font-semibold shrink-0 transition"
              :class="
                idx < currentIndex
                  ? 'bg-primary-700 text-white'
                  : idx === currentIndex
                    ? 'bg-primary-50 text-primary-800 border border-primary-200'
                    : 'bg-ink-100 text-ink-500'
              "
            >
              {{ idx < currentIndex ? '✓' : String(idx + 1).padStart(2, '0') }}
            </span>
            <span
              class="text-xs font-medium hidden md:inline truncate"
              :class="idx === currentIndex ? 'text-ink-900' : 'text-ink-500'"
            >
              {{ t(step.titleKey) }}
            </span>
          </div>
          <span
            v-if="idx < steps.length - 1"
            class="flex-1 h-px"
            :class="idx < currentIndex ? 'bg-primary-300' : 'bg-ink-200'"
          />
        </li>
      </ol>
    </header>

    <!-- Step body -->
    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-8 space-y-6">
      <div>
        <h2 class="text-lg font-semibold text-ink-900">{{ t(current.titleKey) }}</h2>
        <p class="mt-1 text-sm text-ink-500">{{ t(current.blurbKey) }}</p>
      </div>

      <!-- Step 1: project name + slug -->
      <div v-if="current.key === 'project'" class="space-y-4 max-w-lg">
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.projectName') }}</span>
          <input
            v-model="form.name"
            type="text"
            placeholder="PCB Inspection v1"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>
        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.projectSlug') }}</span>
          <input
            v-model="form.slug"
            type="text"
            placeholder="pcb-inspection-v1"
            pattern="[a-z0-9-]+"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white font-mono focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
          <span class="text-xs text-ink-500">{{ t('wizard.slugHint') }}</span>
        </label>
      </div>

      <!-- Step 2: BOM upload -->
      <div v-else-if="current.key === 'bom'" class="space-y-3 max-w-lg">
        <label
          class="flex flex-col items-center justify-center min-h-32 border-2 border-dashed border-ink-300 rounded-xl bg-ink-50 px-6 py-8 cursor-pointer hover:border-primary-400 transition"
        >
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.uploadBom') }}</span>
          <span class="mt-1 text-xs text-ink-500">.xlsx / .csv · SAP ZLMM_BOM_REPORT OK</span>
          <span v-if="form.bomFileName" class="mt-3 text-xs font-mono text-primary-700">
            {{ form.bomFileName }}
          </span>
          <input
            type="file"
            accept=".xlsx,.csv"
            class="hidden"
            @change="onFile('bomFileName', $event)"
          />
        </label>
      </div>

      <!-- Step 3: golden samples -->
      <div v-else-if="current.key === 'golden'" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <label
          v-for="(side, key) in {
            goldenTopName: 'wizard.goldenTop',
            goldenBottomName: 'wizard.goldenBottom',
          }"
          :key="key"
          class="flex flex-col items-center justify-center min-h-40 border-2 border-dashed border-ink-300 rounded-xl bg-ink-50 px-6 py-8 cursor-pointer hover:border-primary-400 transition"
        >
          <span class="text-sm font-medium text-ink-700">{{ t(side) }}</span>
          <span class="mt-1 text-xs text-ink-500">.jpg / .png · ≥1920px</span>
          <span
            v-if="form[key as keyof typeof form]"
            class="mt-3 text-xs font-mono text-primary-700"
          >
            {{ form[key as keyof typeof form] }}
          </span>
          <input
            type="file"
            accept="image/*"
            class="hidden"
            @change="onFile(key as keyof typeof form, $event)"
          />
        </label>
      </div>

      <!-- Step 4: drawing -->
      <div v-else-if="current.key === 'drawing'" class="max-w-lg space-y-3">
        <label
          class="flex flex-col items-center justify-center min-h-40 border-2 border-dashed border-ink-300 rounded-xl bg-ink-50 px-6 py-8 cursor-pointer hover:border-primary-400 transition"
        >
          <span class="text-sm font-medium text-ink-700">{{ t('wizard.uploadDrawing') }}</span>
          <span class="mt-1 text-xs text-ink-500">{{ t('wizard.drawingNote') }}</span>
          <span v-if="form.drawingName" class="mt-3 text-xs font-mono text-primary-700">
            {{ form.drawingName }}
          </span>
          <input
            type="file"
            accept="image/*"
            class="hidden"
            @change="onFile('drawingName', $event)"
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
            <dd class="font-medium text-ink-900">{{ form.name || '—' }}</dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.projectSlug') }}</dt>
            <dd class="font-mono text-ink-900">{{ form.slug || '—' }}</dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">BOM</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">{{ form.bomFileName || '—' }}</dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.goldenTop') }}</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">
              {{ form.goldenTopName || '—' }}
            </dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.goldenBottom') }}</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">
              {{ form.goldenBottomName || '—' }}
            </dd>
          </div>
          <div class="flex justify-between border-b border-ink-100 py-2">
            <dt class="text-ink-500">{{ t('wizard.drawingShort') }}</dt>
            <dd class="font-mono text-ink-900 truncate max-w-[60%]">{{ form.drawingName || '—' }}</dd>
          </div>
        </dl>
        <p
          class="text-xs text-primary-900 bg-primary-50 border border-primary-200 rounded-md px-3 py-2"
        >
          {{ t('wizard.reviewNote') }}
        </p>
      </div>
    </section>

    <!-- Action strip -->
    <footer class="mt-6 flex items-center justify-between">
      <AppButton variant="ghost" :disabled="isFirst" @click="back">
        ← {{ t('common.back') }}
      </AppButton>
      <div class="flex items-center gap-3">
        <span class="text-xs font-mono text-ink-500">
          {{ currentIndex + 1 }} / {{ steps.length }}
        </span>
        <AppButton v-if="!isLast" @click="next">
          {{ t('common.continue') }} →
        </AppButton>
        <AppButton v-else @click="finish">
          {{ t('wizard.finish') }} →
        </AppButton>
      </div>
    </footer>
  </div>
</template>
