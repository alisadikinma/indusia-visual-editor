<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import BomTable from "../components/BomTable.vue";
import PreLabelPanel from "../components/PreLabelPanel.vue";
import { useWizardStore } from "../stores/wizard";

const route = useRoute();
const store = useWizardStore();
const dragActive = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

const projectId = computed(() => String(route.params.id));

onMounted(() => {
  store.fetchBomItems(projectId.value);
});

function onPickClick() {
  fileInputRef.value?.click();
}

async function handleFile(file: File | undefined | null) {
  if (!file) return;
  await store.upload(projectId.value, file);
}

function onChange(e: Event) {
  const input = e.target as HTMLInputElement;
  handleFile(input.files?.[0]);
  // allow same file re-pick (input keeps last value otherwise)
  input.value = "";
}

function onDrop(e: DragEvent) {
  dragActive.value = false;
  handleFile(e.dataTransfer?.files?.[0]);
}

function onDragOver(e: DragEvent) {
  e.preventDefault();
  dragActive.value = true;
}

function onDragLeave() {
  dragActive.value = false;
}
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-8">
    <header class="mb-6">
      <h1 class="font-sans text-3xl font-bold text-text-primary">
        Project Wizard
      </h1>
      <p class="mt-1 text-sm text-text-secondary">
        Project ID:
        <span class="font-mono text-text-tertiary">{{ projectId }}</span>
      </p>
    </header>

    <ol
      class="mb-8 flex items-center gap-4 text-sm"
      aria-label="Wizard steps"
      data-testid="wizard-steps"
    >
      <li class="flex items-center gap-2 font-semibold text-text-primary">
        <span
          class="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-text-on-primary"
        >
          1
        </span>
        BOM Upload
      </li>
      <li class="flex items-center gap-2 text-text-tertiary">
        <span
          class="flex h-6 w-6 items-center justify-center rounded-full border border-border-default"
        >
          2
        </span>
        Golden Sample
      </li>
      <li class="flex items-center gap-2 text-text-tertiary">
        <span
          class="flex h-6 w-6 items-center justify-center rounded-full border border-border-default"
        >
          3
        </span>
        Labeling
      </li>
    </ol>

    <section
      class="mb-6 rounded-md border-2 border-dashed p-8 text-center transition-colors"
      :class="dragActive ? 'border-primary bg-bg-elevated' : 'border-border-default bg-bg-elevated'"
      data-testid="bom-dropzone"
      @drop.prevent="onDrop"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
    >
      <p class="text-text-secondary">
        Tarik file BOM ke sini, atau
        <button
          type="button"
          class="font-semibold text-primary underline hover:text-primary-hover"
          data-testid="bom-pick-button"
          @click="onPickClick"
        >
          pilih file
        </button>
      </p>
      <p class="mt-1 text-xs text-text-tertiary">
        Format: .xlsx, .xlsm, atau .csv. Maks 50 MB.
      </p>
      <input
        ref="fileInputRef"
        type="file"
        accept=".xlsx,.xlsm,.csv"
        class="hidden"
        data-testid="bom-file-input"
        @change="onChange"
      />
    </section>

    <p
      v-if="store.uploading"
      class="mb-4 text-sm text-text-secondary"
      data-testid="upload-status"
    >
      Memproses BOM...
    </p>
    <p
      v-if="store.error"
      class="mb-4 rounded bg-danger/20 px-4 py-2 text-sm text-danger"
      role="alert"
      data-testid="upload-error"
    >
      {{ store.error }}
    </p>

    <BomTable :items="store.items" />

    <section class="mt-8" data-testid="wizard-step-2">
      <h2 class="mb-4 font-sans text-lg font-semibold text-text-primary">
        Langkah 2 — Pre-label Gemma 4
      </h2>
      <p class="mb-3 text-sm text-text-secondary">
        Jalankan asisten pre-label setelah BOM + Golden Sample (atas dan/atau
        bawah) sudah di-upload. Hasilnya akan muncul sebagai bounding box
        pre-draw di labeling canvas.
      </p>
      <div class="grid gap-3 md:grid-cols-2">
        <PreLabelPanel :project-id="projectId" side="top" />
        <PreLabelPanel :project-id="projectId" side="bottom" />
      </div>
    </section>
  </main>
</template>
