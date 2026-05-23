<script setup lang="ts">
/**
 * Gate-1 training-approval panel (Phase 8.3).
 *
 * On mount, calls POST /api/projects/{id}/training/suggest-hyperparams which
 * returns both the dataset stats and a Gemma 4 hyperparameter suggestion in
 * one round-trip. The operator reviews stats + suggestion, then clicks
 * "Mulai Training" to hand off to POST /api/projects/{id}/training/start.
 *
 * Never auto-approve. The button is the literal Gate-1 (CLAUDE.md §11).
 */
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  startTraining,
  suggestHyperparams,
  type HyperparamsSuggestion,
} from "../api/training";

const route = useRoute();
const router = useRouter();

const projectId = computed(() => String(route.params.id));
const side = ref<"top" | "bottom">("top");

const suggestion = ref<HyperparamsSuggestion | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const noLabels = ref(false);
const submitting = ref(false);

const canStart = computed(
  () => suggestion.value !== null && !submitting.value && !noLabels.value,
);

const sideLabel = computed(() => (side.value === "top" ? "Atas" : "Bawah"));

function extractError(e: unknown): { message: string; status: number | null } {
  const resp = (e as {
    response?: { status?: number; data?: { message?: string } };
  }).response;
  const message =
    (typeof resp?.data?.message === "string" && resp.data.message) ||
    (e instanceof Error ? e.message : "Terjadi kesalahan");
  return { message, status: resp?.status ?? null };
}

async function fetchSuggestion() {
  loading.value = true;
  error.value = null;
  noLabels.value = false;
  suggestion.value = null;
  try {
    suggestion.value = await suggestHyperparams(projectId.value, side.value);
  } catch (e) {
    const info = extractError(e);
    if (info.status === 404) {
      noLabels.value = true;
    } else {
      error.value = info.message;
    }
  } finally {
    loading.value = false;
  }
}

async function onStartTraining() {
  if (!canStart.value) return;
  submitting.value = true;
  error.value = null;
  try {
    const run = await startTraining(projectId.value);
    router.push({
      name: "training-progress",
      params: { id: projectId.value, runId: run.id },
    });
  } catch (e) {
    error.value = extractError(e).message;
  } finally {
    submitting.value = false;
  }
}

function pickSide(next: "top" | "bottom") {
  if (next === side.value) return;
  side.value = next;
  fetchSuggestion();
}

onMounted(() => {
  fetchSuggestion();
});

const stats = computed(() => suggestion.value?.stats ?? null);
const hp = computed(() => suggestion.value?.hyperparameters ?? null);
const criteriaEntries = computed(() => {
  const per = stats.value?.per_criterion ?? {};
  return Object.entries(per).map(([name, count]) => ({ name, count }));
});
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-6">
    <header class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="font-sans text-2xl font-bold text-text-primary">
          Persetujuan Training
        </h1>
        <p class="mt-1 text-xs text-text-tertiary">
          Project
          <span class="font-mono text-text-secondary">{{ projectId }}</span>
          — sisi {{ sideLabel }}
        </p>
      </div>

      <div
        class="flex items-center gap-2 rounded-md border border-border-default bg-bg-elevated p-1"
        role="group"
        aria-label="Pilih sisi PCB"
      >
        <button
          type="button"
          class="rounded px-3 py-1 text-xs font-semibold uppercase tracking-wide transition-colors"
          :class="
            side === 'top'
              ? 'bg-primary text-text-on-primary'
              : 'text-text-secondary hover:bg-bg-deep'
          "
          data-testid="gate1-side-top"
          @click="pickSide('top')"
        >
          Atas
        </button>
        <button
          type="button"
          class="rounded px-3 py-1 text-xs font-semibold uppercase tracking-wide transition-colors"
          :class="
            side === 'bottom'
              ? 'bg-primary text-text-on-primary'
              : 'text-text-secondary hover:bg-bg-deep'
          "
          data-testid="gate1-side-bottom"
          @click="pickSide('bottom')"
        >
          Bawah
        </button>
      </div>
    </header>

    <p
      v-if="loading"
      class="mb-4 text-sm text-text-secondary"
      data-testid="gate1-loading"
    >
      Memuat statistik dan saran Gemma 4...
    </p>

    <p
      v-if="error"
      class="mb-4 rounded bg-danger/20 px-4 py-2 text-sm text-danger"
      role="alert"
      data-testid="gate1-error"
    >
      {{ error }}
    </p>

    <section
      v-if="stats"
      class="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4"
      data-testid="gate1-stats"
    >
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          Total Region
        </p>
        <p class="mt-1 text-2xl font-bold text-text-primary">
          {{ stats.total }}
        </p>
      </div>
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          Inspected
        </p>
        <p class="mt-1 text-2xl font-bold text-success">
          {{ stats.inspected }}
        </p>
      </div>
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          Skipped
        </p>
        <p class="mt-1 text-2xl font-bold text-text-secondary">
          {{ stats.skipped }}
        </p>
      </div>
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <p class="text-xs uppercase tracking-wide text-text-tertiary">
          MI / SMT
        </p>
        <p class="mt-1 text-2xl font-bold text-text-primary">
          {{ stats.mi_count }} / {{ stats.smt_count }}
        </p>
      </div>
    </section>

    <section
      v-if="stats"
      class="mb-6 rounded-md border border-border-default bg-bg-elevated p-4"
      data-testid="gate1-criteria"
    >
      <h2 class="mb-3 font-sans text-sm font-semibold text-text-primary">
        Per Kriteria Defect
      </h2>
      <ul class="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
        <li
          v-for="row in criteriaEntries"
          :key="row.name"
          class="flex items-center justify-between rounded bg-bg-deep px-3 py-1.5"
        >
          <span class="font-mono text-xs text-text-secondary">{{
            row.name
          }}</span>
          <span class="font-bold text-text-primary">{{ row.count }}</span>
        </li>
      </ul>
    </section>

    <section
      v-if="hp"
      class="mb-6 rounded-md border border-border-default bg-bg-elevated p-4"
      data-testid="gate1-hyperparams"
    >
      <h2 class="mb-3 font-sans text-sm font-semibold text-text-primary">
        Saran Hyperparameter (Gemma 4)
      </h2>
      <dl class="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt class="text-xs uppercase tracking-wide text-text-tertiary">
            Epochs
          </dt>
          <dd class="mt-1 text-xl font-bold text-text-primary">
            {{ hp.epochs }}
          </dd>
        </div>
        <div>
          <dt class="text-xs uppercase tracking-wide text-text-tertiary">
            Batch Size
          </dt>
          <dd class="mt-1 text-xl font-bold text-text-primary">
            {{ hp.batch_size }}
          </dd>
        </div>
        <div>
          <dt class="text-xs uppercase tracking-wide text-text-tertiary">
            Augmentation
          </dt>
          <dd class="mt-1 text-xl font-bold text-text-primary">
            {{ hp.augmentation_intensity }}
          </dd>
        </div>
      </dl>
      <p class="mt-3 text-xs italic text-text-tertiary">
        {{ hp.notes }}
      </p>
    </section>

    <p
      v-if="noLabels"
      class="mb-6 rounded bg-bg-elevated px-4 py-3 text-sm text-text-secondary"
      data-testid="gate1-empty"
    >
      Belum ada label untuk sisi {{ sideLabel }}. Selesaikan canvas
      labeling lebih dulu sebelum memulai training.
    </p>

    <button
      type="button"
      class="rounded-md bg-primary px-6 py-3 text-sm font-semibold uppercase tracking-wide text-text-on-primary transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="!canStart"
      data-testid="start-training-button"
      @click="onStartTraining"
    >
      <span v-if="submitting">Memulai...</span>
      <span v-else>Mulai Training</span>
    </button>
  </main>
</template>
