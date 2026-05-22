<script setup lang="ts">
import { computed } from "vue";

import { useWizardStore } from "../stores/wizard";

const props = defineProps<{ projectId: string; side: "top" | "bottom" }>();
const store = useWizardStore();

const sideState = computed(() => store.prelabel[props.side]);
const sideLabel = computed(() => (props.side === "top" ? "Atas" : "Bawah"));

function trigger() {
  store.runPreLabel(props.projectId, props.side);
}
</script>

<template>
  <div
    class="rounded-md border border-border-default bg-bg-elevated p-4"
    data-testid="prelabel-panel"
  >
    <header class="mb-3 flex items-center justify-between">
      <h3 class="font-sans text-sm font-semibold text-text-primary">
        Pre-label sisi {{ sideLabel }}
      </h3>
      <button
        type="button"
        class="rounded bg-primary px-3 py-1 text-xs font-semibold uppercase tracking-wide text-text-on-primary transition-colors duration-150 hover:bg-primary-hover disabled:opacity-50"
        :disabled="sideState.loading"
        :data-testid="`prelabel-trigger-${props.side}`"
        @click="trigger"
      >
        {{ sideState.regions.length > 0 ? "Re-run" : "Jalankan" }}
      </button>
    </header>

    <p
      v-if="sideState.loading"
      class="text-sm text-text-secondary"
      data-testid="prelabel-loading"
    >
      Menjalankan Gemma 4...
    </p>

    <p
      v-else-if="sideState.error"
      class="rounded bg-danger/20 px-3 py-2 text-sm text-danger"
      role="alert"
      data-testid="prelabel-error"
    >
      {{ sideState.error }}
    </p>

    <p
      v-else-if="sideState.regions.length === 0"
      class="text-sm text-text-tertiary"
      data-testid="prelabel-empty"
    >
      Belum ada pre-label. Pastikan BOM + Golden Sample sudah di-upload.
    </p>

    <p
      v-else
      class="text-sm text-success"
      data-testid="prelabel-success"
    >
      <strong>{{ sideState.regions.length }}</strong> komponen terdeteksi.
      Lanjut ke labeling canvas untuk review.
    </p>
  </div>
</template>
