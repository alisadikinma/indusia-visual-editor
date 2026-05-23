<script setup lang="ts">
/**
 * Vue 3 wrapper around the Label Studio Frontend (LSF) React 18 island.
 *
 * LSF is loaded as a third-party Apache-2.0 library via <script> tags in
 * web/index.html pointing at /lsf/main.js (vendored in Phase 6.1). After
 * load, `window.LabelStudio` is a constructor we call directly.
 *
 * Boundary (CLAUDE.md §10): we do NOT fork LSF, we do NOT use its
 * datamanager / Django backend / ML Backend protocol. v1 bakes
 * predictions into the task JSON.
 */
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

interface LsfAnnotation {
  serializeAnnotation: () => unknown[];
}

interface LsfInstanceOptions {
  config: string;
  task: unknown;
  interfaces?: string[];
  reactVersion?: string;
  onLabelStudioLoad?: (ls: unknown) => void;
  onSubmitAnnotation?: (ls: unknown, ann: LsfAnnotation) => void;
  onUpdateAnnotation?: (ls: unknown, ann: LsfAnnotation) => void;
  onSkipTask?: (ls: unknown) => void;
}

interface LsfInstance {
  destroy: () => void;
}

type LsfConstructor = new (
  target: HTMLElement,
  options: LsfInstanceOptions,
) => LsfInstance;

const props = withDefaults(
  defineProps<{
    config: string;
    task: unknown;
    interfaces?: string[];
    loadTimeoutMs?: number;
  }>(),
  {
    interfaces: () => [
      "panel",
      "update",
      "submit",
      "controls",
      "side-column",
      "annotations:menu",
      "annotations:current",
    ],
    loadTimeoutMs: 5000,
  },
);

const emit = defineEmits<{
  (e: "submit", annotation: { result: unknown[] }): void;
  (e: "update", annotation: { result: unknown[] }): void;
  (e: "load-error", message: string): void;
  (e: "ready"): void;
}>();

const hostRef = ref<HTMLDivElement | null>(null);
let instance: LsfInstance | null = null;

function resolveLabelStudio(): LsfConstructor | null {
  const w = window as unknown as { LabelStudio?: LsfConstructor };
  return typeof w.LabelStudio === "function" ? w.LabelStudio : null;
}

async function waitForLabelStudio(timeoutMs: number): Promise<LsfConstructor> {
  const start = Date.now();
  const step = 50;
  while (Date.now() - start < timeoutMs) {
    const ctor = resolveLabelStudio();
    if (ctor) return ctor;
    await new Promise((r) => setTimeout(r, step));
  }
  const ctor = resolveLabelStudio();
  if (ctor) return ctor;
  throw new Error(
    `LabelStudio bundle did not load within ${timeoutMs}ms — check /lsf/main.js`,
  );
}

function pack(ann: LsfAnnotation): { result: unknown[] } {
  return { result: ann.serializeAnnotation() };
}

async function mountLsf() {
  if (!hostRef.value) return;
  let ctor: LsfConstructor;
  try {
    ctor = await waitForLabelStudio(props.loadTimeoutMs);
  } catch (err) {
    emit("load-error", err instanceof Error ? err.message : String(err));
    return;
  }

  try {
    instance = new ctor(hostRef.value, {
      config: props.config,
      task: props.task,
      interfaces: props.interfaces,
      reactVersion: "v18",
      onLabelStudioLoad: () => emit("ready"),
      onSubmitAnnotation: (_ls, ann) => emit("submit", pack(ann)),
      onUpdateAnnotation: (_ls, ann) => emit("update", pack(ann)),
    });
  } catch (err) {
    emit(
      "load-error",
      `Failed to construct LabelStudio: ${err instanceof Error ? err.message : String(err)}`,
    );
  }
}

onMounted(() => {
  void mountLsf();
});

onBeforeUnmount(() => {
  if (instance) {
    try {
      instance.destroy();
    } catch (err) {
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.debug("LSF destroy threw:", err);
      }
    }
    instance = null;
  }
});

// React to config/task changes by destroying and re-mounting. LSF doesn't
// expose a public "replace config" API; tear-down + rebuild is the
// supported path.
watch(
  () => [props.config, props.task],
  () => {
    if (instance) {
      try {
        instance.destroy();
      } catch {
        // ignore — fresh mount will replace it anyway
      }
      instance = null;
    }
    void mountLsf();
  },
);
</script>

<template>
  <div
    ref="hostRef"
    class="lsf-host h-full w-full"
    data-testid="lsf-host"
  ></div>
</template>

<style scoped>
.lsf-host {
  min-height: 480px;
}
</style>
