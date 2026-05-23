<script setup lang="ts">
/**
 * Gate-2 promote-to-production panel (Phase 10.4).
 *
 * Renders the eval summary for the current TrainRun side-by-side with the
 * most recent prior deployment (so the operator sees what's currently in
 * production before clicking Promote). The "Promote to Production" button
 * opens a confirmation modal — the modal's confirm action is the literal
 * Gate-2 trigger per CLAUDE.md §11. No auto-approval, ever.
 */
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import {
  getDeployHistory,
  promoteToProduction,
  type Deployment,
} from "../api/deploy";
import { getEval, type EvalResult } from "../api/eval";

const route = useRoute();

const projectId = computed(() => String(route.params.id));
const runId = computed(() => String(route.params.runId));

const evalResult = ref<EvalResult | null>(null);
const prevDeployment = ref<Deployment | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const showModal = ref(false);
const submitting = ref(false);
const successRow = ref<Deployment | null>(null);

function extractError(e: unknown): string {
  const resp = (e as { response?: { data?: { message?: string } } }).response;
  if (typeof resp?.data?.message === "string") return resp.data.message;
  if (e instanceof Error) return e.message;
  return "Terjadi kesalahan saat memuat data";
}

async function fetchContext() {
  loading.value = true;
  error.value = null;
  try {
    const [ev, history] = await Promise.all([
      getEval(runId.value),
      getDeployHistory(projectId.value),
    ]);
    evalResult.value = ev;
    prevDeployment.value =
      history.find((d) => d.status === "succeeded") ?? null;
  } catch (e) {
    error.value = extractError(e);
  } finally {
    loading.value = false;
  }
}

function openModal() {
  showModal.value = true;
}

function cancelModal() {
  showModal.value = false;
}

async function confirmPromote() {
  if (submitting.value) return;
  submitting.value = true;
  error.value = null;
  try {
    successRow.value = await promoteToProduction(projectId.value);
    showModal.value = false;
  } catch (e) {
    error.value = extractError(e);
  } finally {
    submitting.value = false;
  }
}

onMounted(() => {
  fetchContext();
});

const currentMap = computed(() =>
  typeof evalResult.value?.metrics.mAP === "number"
    ? (evalResult.value.metrics.mAP as number)
    : null,
);
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-6">
    <header class="mb-6">
      <h1 class="font-sans text-2xl font-bold text-text-primary">
        Promote ke Production
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
      data-testid="gate2-loading"
    >
      Memuat ringkasan eval dan riwayat deployment...
    </p>

    <p
      v-if="error"
      class="mb-4 rounded bg-danger/20 px-4 py-2 text-sm text-danger"
      role="alert"
      data-testid="gate2-error"
    >
      {{ error }}
    </p>

    <section
      v-if="evalResult"
      class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <h2 class="mb-2 text-xs uppercase tracking-wide text-text-tertiary">
          Run Saat Ini
        </h2>
        <p
          class="text-3xl font-bold text-text-primary"
          data-testid="gate2-current-map"
        >
          mAP {{ currentMap !== null ? currentMap.toFixed(3) : "—" }}
        </p>
        <p class="mt-1 font-mono text-xs text-text-secondary">
          run {{ runId }}
        </p>
      </div>

      <div class="rounded-md border border-border-default bg-bg-elevated p-4">
        <h2 class="mb-2 text-xs uppercase tracking-wide text-text-tertiary">
          Deployment Sebelumnya
        </h2>
        <p
          v-if="prevDeployment"
          class="text-lg font-semibold text-text-primary"
          data-testid="gate2-prev-version"
        >
          {{ prevDeployment.model_version }}
        </p>
        <p
          v-else
          class="text-sm italic text-text-tertiary"
          data-testid="gate2-prev-empty"
        >
          Belum pernah promote — ini bakal jadi deployment pertama.
        </p>
        <p
          v-if="prevDeployment"
          class="mt-1 font-mono text-xs text-text-secondary"
        >
          {{ prevDeployment.deployed_at }}
        </p>
      </div>
    </section>

    <section
      v-if="successRow"
      class="mb-6 rounded-md border border-success/40 bg-success/10 p-4"
      data-testid="promote-success"
    >
      <h2 class="font-sans text-sm font-semibold text-success">
        Promote sukses
      </h2>
      <p class="mt-1 font-mono text-xs text-text-secondary">
        version {{ successRow.model_version }}
      </p>
    </section>

    <button
      v-if="!successRow"
      type="button"
      class="rounded-md bg-danger px-6 py-3 text-sm font-semibold uppercase tracking-wide text-text-on-primary transition-colors hover:bg-danger-hover disabled:cursor-not-allowed disabled:opacity-50"
      :disabled="loading || evalResult === null || submitting"
      data-testid="promote-button"
      @click="openModal"
    >
      Promote ke Production
    </button>

    <!-- Confirmation modal -->
    <div
      v-if="showModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-bg-deep/80 p-4"
      data-testid="confirm-modal"
      role="dialog"
      aria-modal="true"
    >
      <div
        class="w-full max-w-md rounded-lg border border-danger/40 bg-bg-elevated p-6 shadow-xl"
      >
        <h2 class="font-sans text-lg font-bold text-text-primary">
          Konfirmasi Promote
        </h2>
        <p class="mt-3 text-sm text-text-secondary">
          Yakin mau push bobot ke registry production? Edge nodes bakal
          consume model baru ini setelah notify webhook (M11).
        </p>
        <p class="mt-3 text-xs italic text-text-tertiary">
          Aksi ini bisa di-rollback via pin version per-edge, tapi history
          deployment permanent di database.
        </p>

        <div class="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            class="rounded-md border border-border-default px-4 py-2 text-sm text-text-secondary hover:bg-bg-deep"
            data-testid="confirm-modal-cancel"
            :disabled="submitting"
            @click="cancelModal"
          >
            Batal
          </button>
          <button
            type="button"
            class="rounded-md bg-danger px-4 py-2 text-sm font-semibold text-text-on-primary hover:bg-danger-hover disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="confirm-modal-confirm"
            :disabled="submitting"
            @click="confirmPromote"
          >
            <span v-if="submitting">Mempromote...</span>
            <span v-else>Ya, Promote</span>
          </button>
        </div>
      </div>
    </div>
  </main>
</template>
