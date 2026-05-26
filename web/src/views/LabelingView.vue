<script setup lang="ts">
/**
 * Labeling canvas page (M6 Phase 6.5).
 *
 * Fetches the LSF task JSON + config from
 * GET /api/projects/{id}/labels/task?side=<top|bottom>, hands them to
 * LSFEmbed, and forwards onSubmit annotations to
 * POST /api/projects/{id}/labels?side=<…>.
 *
 * Side toggle re-fetches; latest version per side surfaces in the
 * save indicator.
 */
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import LSFEmbed from "../components/LSFEmbed.vue";
import { useLabelsStore } from "../stores/labels";

const route = useRoute();
const store = useLabelsStore();

const projectId = computed(() => String(route.params.id));
const currentSide = ref<"top" | "bottom">("top");

onMounted(() => {
  store.fetchTask(projectId.value, currentSide.value);
});

watch(currentSide, (next) => {
  store.fetchTask(projectId.value, next);
});

function pickSide(side: "top" | "bottom") {
  if (side === currentSide.value) return;
  currentSide.value = side;
}

function onSubmit(annotation: { result: unknown[] }) {
  store.submit(projectId.value, annotation);
}

function refreshPredictions() {
  store.refreshPredictions(projectId.value);
}

function onUpdate(_annotation: { result: unknown[] }) {
  // Live-update hook — wired so future "skipped-region dim" CSS overlay
  // can subscribe without re-architecting. Intentionally empty for v1.
}

function onLoadError(message: string) {
  store.error = message;
}
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-6">
    <header class="mb-4 flex items-center justify-between">
      <div>
        <h1 class="font-sans text-2xl font-bold text-text-primary">
          Labeling Canvas
        </h1>
        <p class="mt-1 text-xs text-text-tertiary">
          Project
          <span class="font-mono text-text-secondary">{{ projectId }}</span>
        </p>
      </div>

      <div class="flex items-center gap-3">
      <button
        type="button"
        class="rounded-md border border-border-default bg-bg-elevated px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-text-primary transition-colors hover:bg-bg-deep disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="store.refreshing || store.loading || !store.task"
        data-testid="refresh-predictions"
        @click="refreshPredictions"
      >
        Muat ulang prediksi
      </button>

      <div
        class="flex items-center gap-2 rounded-md border border-border-default bg-bg-elevated p-1"
        role="group"
        aria-label="Pilih sisi PCB"
      >
        <button
          type="button"
          class="rounded px-3 py-1 text-xs font-semibold uppercase tracking-wide transition-colors"
          :class="
            currentSide === 'top'
              ? 'bg-primary text-text-on-primary'
              : 'text-text-secondary hover:bg-bg-deep'
          "
          data-testid="side-toggle-top"
          @click="pickSide('top')"
        >
          Atas
        </button>
        <button
          type="button"
          class="rounded px-3 py-1 text-xs font-semibold uppercase tracking-wide transition-colors"
          :class="
            currentSide === 'bottom'
              ? 'bg-primary text-text-on-primary'
              : 'text-text-secondary hover:bg-bg-deep'
          "
          data-testid="side-toggle-bottom"
          @click="pickSide('bottom')"
        >
          Bawah
        </button>
      </div>
      </div>
    </header>

    <p
      v-if="store.refreshing"
      class="mb-4 text-sm text-text-secondary"
      data-testid="refreshing-indicator"
    >
      Membuat prediksi baru dari Gemma...
    </p>

    <p
      v-if="store.loading"
      class="mb-4 text-sm text-text-secondary"
      data-testid="labeling-loading"
    >
      Memuat task...
    </p>

    <p
      v-if="store.error"
      class="mb-4 rounded bg-danger/20 px-4 py-2 text-sm text-danger"
      role="alert"
      data-testid="labeling-error"
    >
      {{ store.error }}
    </p>

    <p
      v-if="store.latest"
      class="mb-3 inline-block rounded bg-success/20 px-3 py-1 text-xs font-semibold text-success"
      data-testid="save-indicator"
    >
      Tersimpan — sisi {{ store.latest.side }} v{{ store.latest.version }}
    </p>

    <p
      v-if="store.saving"
      class="mb-3 text-xs text-text-tertiary"
      data-testid="saving-indicator"
    >
      Menyimpan...
    </p>

    <section
      class="overflow-hidden rounded-md border border-border-default bg-bg-elevated"
      data-testid="labeling-canvas"
    >
      <LSFEmbed
        v-if="store.task"
        :config="store.task.config"
        :task="store.task.task"
        @submit="onSubmit"
        @update="onUpdate"
        @load-error="onLoadError"
      />
      <div
        v-else-if="!store.loading && !store.error"
        class="p-8 text-center text-sm text-text-tertiary"
      >
        Belum ada task aktif.
      </div>
    </section>
  </main>
</template>

<style scoped>
/*
 * Skipped-region dim overlay (LSF emits region.classifications on update).
 * We tag the rendered region with .ive-region-skipped via a future watcher
 * on store.task; this rule supplies the visual treatment.
 */
:deep(.ive-region-skipped) {
  opacity: 0.35;
  filter: grayscale(0.4);
}
</style>
