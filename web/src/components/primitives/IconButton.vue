<script setup lang="ts">
type Variant = 'default' | 'ghost' | 'danger' | 'primary'
type Size = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  { variant: 'ghost', size: 'md', type: 'button', disabled: false },
)

const variantClasses: Record<Variant, string> = {
  default: 'bg-surface-canvas text-ink-700 hover:bg-ink-100 border border-border-default',
  ghost: 'bg-transparent text-ink-600 hover:bg-ink-100 hover:text-ink-900',
  danger: 'bg-transparent text-red-600 hover:bg-red-50',
  primary: 'bg-primary-600 text-white hover:bg-primary-700',
}

const sizeClasses: Record<Size, string> = {
  sm: 'h-8 w-8',
  md: 'h-9 w-9',
  lg: 'h-10 w-10',
}
</script>

<template>
  <button
    data-testid="icon-button"
    :type="props.type"
    :disabled="props.disabled"
    :class="[
      'inline-flex items-center justify-center rounded-md transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600',
      'disabled:cursor-not-allowed disabled:opacity-50',
      variantClasses[props.variant],
      sizeClasses[props.size],
    ]"
  >
    <slot />
  </button>
</template>
