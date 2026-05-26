<script setup lang="ts">
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  {
    variant: 'primary',
    size: 'md',
    type: 'button',
    disabled: false,
  },
)

const variantClasses: Record<Variant, string> = {
  primary: 'bg-primary-700 hover:bg-primary-800 text-white shadow-card',
  secondary: 'bg-ink-100 hover:bg-ink-200 text-ink-900',
  ghost: 'bg-transparent hover:bg-ink-100 text-ink-700',
  danger: 'bg-danger hover:bg-red-700 text-white shadow-card',
}

const sizeClasses: Record<Size, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
}
</script>

<template>
  <button
    :type="props.type"
    :disabled="props.disabled"
    :class="[
      'inline-flex items-center justify-center gap-2 rounded-md font-medium transition',
      'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600',
      'disabled:cursor-not-allowed disabled:opacity-50',
      variantClasses[props.variant],
      sizeClasses[props.size],
    ]"
  >
    <slot />
  </button>
</template>
