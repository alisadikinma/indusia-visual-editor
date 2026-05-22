<script setup lang="ts">
import { useRoute } from "vue-router";

// Phase 1.4 placeholder. The real wizard ships in Phase 2.3 (BOM upload),
// M5 (pre-label), and M6 (labeling canvas) — see plan §M2–§M6.
const route = useRoute();
</script>

<template>
  <main class="min-h-screen bg-bg-deep p-8">
    <h1 class="font-sans text-3xl font-bold text-text-primary">Project Wizard</h1>
    <p class="mt-2 text-text-secondary">
      Project ID: <span class="font-mono">{{ route.params.id }}</span>
    </p>
    <p class="mt-4 text-text-tertiary">
      Wizard UI akan tersedia di Phase 2.3 (BOM upload) ke atas.
    </p>
  </main>
</template>
