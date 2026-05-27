<script setup lang="ts">
type Orientation = 'horizontal' | 'vertical'

const props = withDefaults(
  defineProps<{
    orientation?: Orientation
    label?: string
  }>(),
  { orientation: 'horizontal' },
)
</script>

<template>
  <div
    v-if="props.orientation === 'horizontal'"
    data-testid="app-divider"
    data-orientation="horizontal"
    role="separator"
    aria-orientation="horizontal"
    class="flex items-center gap-3"
  >
    <span class="h-px flex-1 bg-border-default" />
    <span
      v-if="props.label"
      class="text-xs uppercase tracking-wide text-ink-500"
    >{{ props.label }}</span>
    <span v-if="props.label" class="h-px flex-1 bg-border-default" />
  </div>
  <div
    v-else
    data-testid="app-divider"
    data-orientation="vertical"
    role="separator"
    aria-orientation="vertical"
    class="inline-flex h-full w-px bg-border-default"
  />
</template>
