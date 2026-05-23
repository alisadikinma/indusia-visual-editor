<script setup lang="ts">
/**
 * Eval view (M9 Phase 9.2).
 *
 * Loads /api/training/{runId}/eval on mount. Renders mAP + per-component
 * F1 (via MetricChart), the worst false-positive / false-negative grid
 * (via PredictionGrid), and delta indicators vs the previous succeeded
 * run for the same project.
 */
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { getEval, type EvalResult } from "../api/eval";
import MetricChart from "../components/MetricChart.vue";
import PredictionGrid from "../components/PredictionGrid.vue";

const route = useRoute();

const runId = computed(() => String(route.params.runId));
const projectId = computed(() => String(route.params.id));

const result = ref<EvalResult | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

function extractError(e: unknown): string {
  const resp = (e as { response?: { data?: { message?: string } } }).response;
  if (typeof resp?.data?.message === "string") return resp.data.message;
  if (e instanceof Error) return e.message;
  return "Terjadi kesalahan saat memuat hasil eval";
}

async function fetchEval() {
  loading.value = true;
  error.value = null;
  try {
    result.value = await getEval(runId.value);
  } catch (e) {
    error.value = extractError(e);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchEval();
});

const currentMap = computed(() =>
  typeof result.value?.metrics.mAP === "number"
    ? (result.value.metrics.mAP as number)
    : null,
);
const prevMap = computed(() =>
  typeof result.value?.prev_metrics?.mAP === "number"
    ? (result.value.prev_metrics.mAP as number)
    : null,
);

const mapDelta = computed<number | null>(() => {
  if (currentMap.value === null || prevMap.value === null) return null;
  return currentMap.value - prevMap.value;
});

const deltaArrow = computed(() => {
  const d = mapDelta.value;
  if (d === null) return "";
  if (d > 0) return "▲";
  if (d < 0) return "▼";
  return "■";
});

const deltaClass = computed(() => {
  const d = mapDelta.value;
  if (d === null) return "";
  if (d > 0) return "text-success";
  if (d < 0) return "text-warning";
  return "text-text-secondary";
});

const f1 = computed<Record<string, number>>(() => {
  const v = result.value?.metrics.per_component_f1;
  return v && typeof v === "object" ? (v as Record<string, number>) : {};
});

const prevF1 = computed<Record<string, number> | null>(() => {
  const v = result.value?.prev_metrics?.per_component_f1;
  return v && typeof v === "object" ? (v as Record<string, number>) : null;
});
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-6">
    <header class="mb-6">
      <h1 class="font-sans text-2xl font-bold text-text-primary">
        Hasil Eval Training
      </h1>
      <p class="mt-1 text-xs text-text-tertiary">
        Project
        <span class="font-mono text-text-secondary">{{ projectId }}</span>
        — Run
        <span class="font-mono text-text-secondary">{{ runId }}</span>
      </p>
    </header>

    <p
      v-if="loading"
      class="mb-4 text-sm text-text-secondary"
      data-testid="eval-loading"
    >
      Memuat hasil eval...
    </p>

    <p
      v-if="error"
      class="mb-4 rounded bg-danger/20 px-4 py-2 text-sm text-danger"
      role="alert"
      data-testid="eval-error"
    >
      {{ error }}
    </p>

    <section
      v-if="result && currentMap !== null"
      class="mb-6 flex flex-wrap items-end gap-6"
    >
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          mAP (Run Ini)
        </p>
        <p
          class="mt-1 text-3xl font-bold text-text-primary"
          data-testid="eval-map"
        >
          {{ currentMap.toFixed(3) }}
        </p>
      </div>

      <div
        v-if="mapDelta !== null"
        class="flex items-center gap-2 rounded-md border border-border-default bg-bg-elevated px-4 py-3"
        :class="deltaClass"
        data-testid="eval-map-delta"
      >
        <span class="text-2xl font-bold">{{ deltaArrow }}</span>
        <span class="font-mono text-sm font-bold">
          {{ mapDelta > 0 ? "+" : "" }}{{ mapDelta.toFixed(2) }}
        </span>
        <span class="text-xs uppercase tracking-wide text-text-tertiary">
          vs run sebelumnya
        </span>
      </div>

      <p
        v-else-if="result.prev_metrics === null"
        class="rounded bg-bg-elevated px-4 py-3 text-xs text-text-secondary"
        data-testid="eval-no-prev"
      >
        Ini run sukses pertama untuk project ini — belum ada pembanding sebelumnya.
      </p>
    </section>

    <section
      v-if="result && Object.keys(f1).length > 0"
      class="mb-6 rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <h2 class="mb-3 font-sans text-sm font-semibold text-text-primary">
        Per-Component F1
      </h2>
      <MetricChart :f1="f1" :prev-f1="prevF1" />
    </section>

    <section
      v-if="result"
      class="rounded-md border border-border-default bg-bg-elevated p-4"
    >
      <h2 class="mb-3 font-sans text-sm font-semibold text-text-primary">
        Prediksi Bermasalah
      </h2>
      <PredictionGrid :predictions="result.predictions" />
    </section>
  </main>
</template>
