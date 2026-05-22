<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { useProjectsStore } from "../stores/projects";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
}>();

const router = useRouter();
const store = useProjectsStore();

const name = ref("");
const error = ref<string | null>(null);
const submitting = ref(false);

function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

const slug = computed(() => slugify(name.value));

watch(
  () => props.open,
  (isOpen) => {
    if (!isOpen) {
      name.value = "";
      error.value = null;
    }
  },
);

async function submit() {
  if (!name.value.trim() || !slug.value) {
    error.value = "Nama project wajib diisi.";
    return;
  }
  submitting.value = true;
  error.value = null;
  try {
    const created = await store.create({ name: name.value.trim(), slug: slug.value });
    emit("update:open", false);
    router.push(`/projects/${created.id}/wizard`);
  } catch (e: unknown) {
    if (e instanceof Error) {
      error.value = e.message;
    } else {
      error.value = "Gagal membuat project. Coba lagi.";
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-bg-deep/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="project-create-title"
    >
      <div
        class="w-full max-w-md rounded-md border border-border-default bg-bg-elevated p-6 shadow-2xl"
      >
        <h2
          id="project-create-title"
          class="font-sans text-xl font-semibold text-text-primary"
        >
          Project Baru
        </h2>
        <p class="mt-2 text-sm text-text-secondary">
          Beri nama project sesuai PCB model code dari customer.
        </p>

        <form class="mt-6 space-y-4" @submit.prevent="submit">
          <label class="block">
            <span class="text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Nama project
            </span>
            <input
              v-model="name"
              data-testid="project-name-input"
              type="text"
              autocomplete="off"
              required
              :disabled="submitting"
              class="mt-1 w-full rounded border border-border-default bg-bg-base px-3 py-2 font-sans text-text-primary placeholder-text-tertiary outline-none focus:border-border-focus focus:ring-2 focus:ring-border-focus/40"
              placeholder="NV80-017542-0501"
            />
          </label>

          <div>
            <span class="text-xs font-semibold uppercase tracking-wide text-text-secondary">
              Slug otomatis
            </span>
            <p class="mt-1 font-mono text-sm text-text-tertiary" data-testid="slug-preview">
              {{ slug || "—" }}
            </p>
          </div>

          <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

          <div class="flex justify-end gap-3 pt-2">
            <button
              type="button"
              :disabled="submitting"
              class="rounded px-4 py-2 text-sm font-semibold uppercase tracking-wide text-text-secondary hover:text-text-primary"
              @click="emit('update:open', false)"
            >
              Batal
            </button>
            <button
              type="submit"
              :disabled="submitting"
              data-testid="project-create-submit"
              class="rounded bg-primary px-4 py-2 text-sm font-semibold uppercase tracking-wide text-text-on-primary transition-colors duration-150 hover:bg-primary-hover disabled:opacity-50"
            >
              {{ submitting ? "Membuat..." : "Buat Project" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>
