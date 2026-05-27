<script setup lang="ts">
defineProps<{
  title: string
  description?: string
}>()
</script>

<template>
  <div
    data-testid="empty-state"
    class="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border-default bg-surface-raised px-6 py-10 text-center"
  >
    <div v-if="$slots.icon" class="text-ink-400">
      <slot name="icon" />
    </div>
    <h3 class="text-base font-semibold text-ink-900">{{ title }}</h3>
    <p v-if="description" class="max-w-md text-sm text-ink-600">{{ description }}</p>
    <div v-if="$slots.action" class="mt-2">
      <slot name="action" />
    </div>
  </div>
</template>
