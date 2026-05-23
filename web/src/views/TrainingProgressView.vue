<script setup lang="ts">
/**
 * Training progress view (Phase 8.4).
 *
 * Subscribes to GET /api/training/{runId}/stream via EventSource and
 * renders progress events as they arrive: current epoch, loss/mAP,
 * terminal state badge. On `succeeded` it stays on-page (M9 eval view
 * is the next destination but isn't built yet — operator clicks
 * through manually when M9 ships).
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { streamProgressUrl } from "../api/training";

type EventPayload = {
  event:
    | "running"
    | "epoch"
    | "succeeded"
    | "failed"
    | "cancelled"
    | "error";
  epoch?: number;
  loss?: number;
  mAP?: number;
  error?: string;
  metrics?: Record<string, unknown>;
};

const route = useRoute();

const runId = computed(() => String(route.params.runId));
const projectId = computed(() => String(route.params.id));

const status = ref<
  "pending" | "running" | "succeeded" | "failed" | "cancelled" | "error"
>("pending");
const currentEpoch = ref<number | null>(null);
const lastLoss = ref<number | null>(null);
const lastMAP = ref<number | null>(null);
const errorMessage = ref<string | null>(null);
const metrics = ref<Record<string, unknown> | null>(null);
const history = ref<EventPayload[]>([]);

let source: EventSource | null = null;
const TERMINAL: ReadonlySet<EventPayload["event"]> = new Set([
  "succeeded",
  "failed",
  "cancelled",
  "error",
]);

function closeStream() {
  if (source) {
    source.close();
    source = null;
  }
}

function handleEvent(ev: { data: string }) {
  let payload: EventPayload;
  try {
    payload = JSON.parse(ev.data) as EventPayload;
  } catch {
    // Malformed stream chunk — surface as error without killing the page.
    errorMessage.value = "Event tidak terbaca dari server";
    status.value = "error";
    closeStream();
    return;
  }
  history.value = [...history.value, payload];

  if (payload.event === "running") {
    status.value = "running";
  }
  if (typeof payload.epoch === "number") currentEpoch.value = payload.epoch;
  if (typeof payload.loss === "number") lastLoss.value = payload.loss;
  if (typeof payload.mAP === "number") lastMAP.value = payload.mAP;

  if (payload.event === "succeeded") {
    status.value = "succeeded";
    metrics.value = payload.metrics ?? null;
    closeStream();
  } else if (payload.event === "failed") {
    status.value = "failed";
    errorMessage.value = payload.error ?? "training failed";
    closeStream();
  } else if (payload.event === "cancelled") {
    status.value = "cancelled";
    closeStream();
  } else if (payload.event === "error") {
    status.value = "error";
    errorMessage.value = payload.error ?? "stream error";
    closeStream();
  }
}

function handleError() {
  if (status.value !== "succeeded" && !TERMINAL.has(status.value as never)) {
    errorMessage.value = "Koneksi ke server training terputus";
    status.value = "error";
  }
  closeStream();
}

onMounted(() => {
  source = new EventSource(streamProgressUrl(runId.value));
  source.onmessage = handleEvent;
  source.onerror = handleError;
});

onBeforeUnmount(() => {
  closeStream();
});

const statusLabel = computed(() => status.value);
const isTerminal = computed(() => TERMINAL.has(status.value as never));
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-6">
    <header class="mb-6">
      <h1 class="font-sans text-2xl font-bold text-text-primary">
        Training Berjalan
      </h1>
      <p class="mt-1 text-xs text-text-tertiary">
        Project
        <span class="font-mono text-text-secondary">{{ projectId }}</span>
        — Run
        <span class="font-mono text-text-secondary">{{ runId }}</span>
      </p>
    </header>

    <section class="mb-6 flex items-center gap-3">
      <span class="text-xs uppercase tracking-wide text-text-tertiary">
        Status
      </span>
      <span
        class="rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide"
        :class="{
          'bg-text-tertiary/20 text-text-secondary': status === 'pending',
          'bg-primary/20 text-primary': status === 'running',
          'bg-success/20 text-success': status === 'succeeded',
          'bg-danger/20 text-danger':
            status === 'failed' || status === 'error',
          'bg-warning/20 text-warning': status === 'cancelled',
        }"
        data-testid="status-badge"
      >
        {{ statusLabel }}
      </span>
    </section>

    <section
      class="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3"
      data-testid="training-metrics"
    >
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          Epoch Saat Ini
        </p>
        <p class="mt-1 text-2xl font-bold text-text-primary">
          {{ currentEpoch ?? "—" }}
        </p>
      </div>
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          Loss Terakhir
        </p>
        <p class="mt-1 text-2xl font-bold text-text-primary">
          {{ lastLoss !== null ? lastLoss.toFixed(4) : "—" }}
        </p>
      </div>
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          mAP Terakhir
        </p>
        <p class="mt-1 text-2xl font-bold text-text-primary">
          {{ lastMAP !== null ? lastMAP.toFixed(3) : "—" }}
        </p>
      </div>
    </section>

    <section
      v-if="errorMessage"
      class="mb-6 rounded bg-danger/20 px-4 py-3 text-sm text-danger"
      role="alert"
      data-testid="training-error"
    >
      {{ errorMessage }}
    </section>

    <section
      v-if="metrics && isTerminal && status === 'succeeded'"
      class="mb-6 rounded-md border border-border-default bg-bg-elevated p-4"
      data-testid="training-metrics-final"
    >
      <h2 class="mb-2 font-sans text-sm font-semibold text-text-primary">
        Metrics Akhir
      </h2>
      <pre
        class="overflow-x-auto rounded bg-bg-deep p-3 text-xs text-text-secondary"
      >{{ JSON.stringify(metrics, null, 2) }}</pre>
    </section>

    <section
      v-if="history.length > 0"
      class="rounded-md border border-border-default bg-bg-elevated p-4"
      data-testid="training-history"
    >
      <h2 class="mb-2 font-sans text-sm font-semibold text-text-primary">
        Riwayat Event
      </h2>
      <ul class="space-y-1 text-xs text-text-secondary">
        <li
          v-for="(ev, i) in history"
          :key="i"
          class="rounded bg-bg-deep px-3 py-1.5 font-mono"
        >
          <strong>{{ ev.event }}</strong>
          <span v-if="ev.epoch !== undefined"> · epoch {{ ev.epoch }}</span>
          <span v-if="ev.loss !== undefined">
            · loss {{ ev.loss.toFixed(4) }}</span
          >
          <span v-if="ev.mAP !== undefined"> · mAP {{ ev.mAP.toFixed(3) }}</span>
        </li>
      </ul>
    </section>
  </main>
</template>
