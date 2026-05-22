<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { useProjectsStore } from "../stores/projects";
import ProjectCreateDialog from "../components/ProjectCreateDialog.vue";
import StatusBadge from "../components/StatusBadge.vue";

const store = useProjectsStore();
const dialogOpen = ref(false);

onMounted(() => {
  store.fetch();
});

const isEmpty = computed(() => !store.loading && store.items.length === 0);

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const min = Math.round(diffMs / 60000);
  if (min < 1) return "barusan";
  if (min < 60) return `${min} menit lalu`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr} jam lalu`;
  const day = Math.round(hr / 24);
  return `${day} hari lalu`;
}
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-8">
    <header class="mb-6 flex items-center justify-between">
      <h1 class="font-sans text-3xl font-bold text-text-primary">Projects</h1>
      <button
        type="button"
        data-testid="new-project-button"
        class="rounded bg-primary px-4 py-2 text-sm font-semibold uppercase tracking-wide text-text-on-primary transition-colors duration-150 hover:bg-primary-hover"
        @click="dialogOpen = true"
      >
        + Project Baru
      </button>
    </header>

    <section
      class="rounded-md border border-border-default bg-bg-elevated"
      aria-label="Daftar project"
    >
      <p v-if="store.loading" class="p-8 text-center text-text-secondary">
        Memuat...
      </p>

      <p v-else-if="store.error" class="p-8 text-center text-danger" role="alert">
        {{ store.error }}
      </p>

      <div v-else-if="isEmpty" class="p-12 text-center" data-testid="empty-state">
        <p class="text-text-secondary">
          Belum ada project. Mulai dengan upload BOM dan Golden Sample.
        </p>
      </div>

      <table v-else class="w-full text-left">
        <thead>
          <tr class="border-b border-border-default">
            <th
              class="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-secondary"
            >
              Nama
            </th>
            <th
              class="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-secondary"
            >
              Slug
            </th>
            <th
              class="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-secondary"
            >
              Status
            </th>
            <th
              class="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-text-secondary"
            >
              Diperbarui
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="project in store.items"
            :key="project.id"
            data-testid="project-row"
            class="border-b border-border-default transition-colors hover:bg-bg-hover"
          >
            <td class="px-4 py-3 text-text-primary">{{ project.name }}</td>
            <td class="px-4 py-3 font-mono text-sm text-text-secondary">
              {{ project.slug }}
            </td>
            <td class="px-4 py-3">
              <StatusBadge :status="project.status" />
            </td>
            <td class="px-4 py-3 text-xs text-text-tertiary">
              {{ relativeTime(project.updated_at) }}
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <ProjectCreateDialog v-model:open="dialogOpen" />
  </main>
</template>
