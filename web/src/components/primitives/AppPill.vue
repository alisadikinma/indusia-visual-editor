<script setup lang="ts">
type Size = 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    selected?: boolean
    size?: Size
    disabled?: boolean
  }>(),
  { selected: false, size: 'md', disabled: false },
)

defineEmits<{ (e: 'click', ev: MouseEvent): void }>()

const sizeClasses: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs',
  md: 'h-8 px-3 text-sm',
}
</script>

<template>
  <button
    type="button"
    data-testid="app-pill"
    :data-selected="props.selected ? 'true' : 'false'"
    :disabled="props.disabled"
    :class="[
      'inline-flex items-center gap-1.5 rounded-full font-medium transition-colors',
      'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600',
      'disabled:cursor-not-allowed disabled:opacity-50',
      props.selected
        ? 'bg-primary-600 text-white'
        : 'bg-surface-raised text-ink-700 hover:bg-ink-100',
      sizeClasses[props.size],
    ]"
    @click="(ev) => $emit('click', ev)"
  >
    <slot />
  </button>
</template>
