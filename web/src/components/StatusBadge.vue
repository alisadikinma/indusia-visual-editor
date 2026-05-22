<script setup lang="ts">
import { computed } from "vue";
import type { ProjectStatus } from "../api/projects";

const props = defineProps<{ status: ProjectStatus }>();

const LABELS: Record<ProjectStatus, string> = {
  drafting: "Drafting",
  training: "Training",
  deployed: "Deployed",
  failed: "Failed",
};

const VARIANT: Record<ProjectStatus, string> = {
  drafting: "bg-secondary/20 text-secondary",
  training: "bg-warning/20 text-warning animate-pulse",
  deployed: "bg-success/20 text-success",
  failed: "bg-danger/20 text-danger",
};

const label = computed(() => LABELS[props.status]);
const variant = computed(() => VARIANT[props.status]);
</script>

<template>
  <span
    data-testid="status-badge"
    :class="[
      'rounded-full px-2.5 py-1 text-xs font-semibold tracking-wide',
      variant,
    ]"
  >
    {{ label }}
  </span>
</template>
