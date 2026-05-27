<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

// LSF (Label Studio Frontend) global. The vendored build attaches a
// LabelStudio constructor onto `window`. We narrow to the bits we use.
declare global {
  interface Window {
    LabelStudio?: new (
      el: HTMLElement,
      options: Record<string, unknown>,
    ) => unknown
    __ive_lsf_loading?: Promise<void>
  }
}

interface LsfTask {
  id: number
  data: { image: string }
  predictions: unknown[]
  annotations: unknown[]
}

const props = defineProps<{
  config: string
  task: LsfTask
}>()

const emit = defineEmits<{
  submit: [lsJson: unknown]
  update: [lsJson: unknown]
  regionSelected: [region: Record<string, unknown> | null]
  ready: []
  error: [message: string]
}>()

const rootEl = ref<HTMLDivElement | null>(null)
const lsInstance = ref<unknown>(null)
const loadFailed = ref(false)

function loadAssets(): Promise<void> {
  if (window.__ive_lsf_loading) return window.__ive_lsf_loading
  if (window.LabelStudio) return Promise.resolve()

  const promise = new Promise<void>((resolve, reject) => {
    if (!document.querySelector('link[data-ive-lsf]')) {
      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = '/lsf/main.css'
      link.dataset.iveLsf = '1'
      document.head.appendChild(link)
    }
    const existing = document.querySelector(
      'script[data-ive-lsf]',
    ) as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('LSF script failed to load')))
      return
    }
    const script = document.createElement('script')
    script.src = '/lsf/main.js'
    script.async = true
    script.dataset.iveLsf = '1'
    script.addEventListener('load', () => resolve())
    script.addEventListener('error', () => reject(new Error('LSF script failed to load')))
    document.head.appendChild(script)
  })
  window.__ive_lsf_loading = promise
  return promise
}

async function instantiate() {
  if (!rootEl.value) return
  try {
    await loadAssets()
  } catch (err) {
    loadFailed.value = true
    emit('error', (err as Error).message)
    return
  }
  // Poll briefly — some vendored bundles attach the global slightly after onload.
  for (let i = 0; i < 50 && !window.LabelStudio; i++) {
    await new Promise((r) => setTimeout(r, 50))
  }
  if (!window.LabelStudio) {
    loadFailed.value = true
    emit('error', 'window.LabelStudio not found after /lsf/main.js loaded')
    return
  }
  // Tear down any previous instance before re-mounting.
  destroy()
  rootEl.value.innerHTML = ''

  const instance = new window.LabelStudio(rootEl.value, {
    config: props.config,
    task: props.task,
    interfaces: [
      'panel',
      'controls',
      'side-column',
      'annotations:menu',
      'annotations:add-new',
      'annotations:current',
      'predictions:menu',
      'topbar',
      'instruction',
    ],
    instanceOptions: { reactVersion: 'v18' },
    onSubmitAnnotation: (_ls: unknown, annotation: { serializeAnnotation: () => unknown }) => {
      emit('submit', annotation.serializeAnnotation())
    },
    onUpdateAnnotation: (_ls: unknown, annotation: { serializeAnnotation: () => unknown }) => {
      emit('update', annotation.serializeAnnotation())
    },
    onSelectAnnotation: (_ls: unknown, _ann: unknown) => {
      emit('regionSelected', null)
    },
    onEntityCreate: (region: Record<string, unknown>) => {
      emit('regionSelected', region)
    },
    onEntityDelete: () => {
      emit('regionSelected', null)
    },
    onLabelStudioLoad: () => {
      emit('ready')
    },
  })
  lsInstance.value = instance
}

function destroy() {
  const inst = lsInstance.value as { destroy?: () => void } | null
  if (inst?.destroy) {
    try {
      inst.destroy()
    } catch {
      /* ignore */
    }
  }
  lsInstance.value = null
}

onMounted(() => {
  instantiate()
})

onBeforeUnmount(() => {
  destroy()
})

// Rebuild instance when task or config changes
watch(
  () => [props.task?.id, props.config] as const,
  (next, prev) => {
    if (!prev || next[0] !== prev[0] || next[1] !== prev[1]) {
      instantiate()
    }
  },
)
</script>

<template>
  <div class="relative h-full w-full bg-ink-100">
    <div ref="rootEl" class="absolute inset-0 ive-lsf-host" />
    <div
      v-if="loadFailed"
      class="absolute inset-0 grid place-items-center bg-ink-50/90 backdrop-blur-sm p-6"
    >
      <div class="max-w-md text-center space-y-2">
        <p class="text-sm font-semibold text-red-700">Label Studio failed to load.</p>
        <p class="text-xs text-ink-500">
          Verify that <code class="font-mono">/lsf/main.js</code> and
          <code class="font-mono">/lsf/main.css</code> are reachable from the dev server.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ive-lsf-host :deep(.lsf-main-view),
.ive-lsf-host :deep(.lsf-main) {
  height: 100% !important;
}
</style>
