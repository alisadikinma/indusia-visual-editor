<script setup lang="ts">
type Variant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'engineer' | 'primary'
type Size = 'sm' | 'md'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    size?: Size
  }>(),
  { variant: 'neutral', size: 'sm' },
)

const variantClasses: Record<Variant, string> = {
  success: 'bg-status-success-subtle text-primary-700 ring-primary-200',
  warning: 'bg-status-warning-subtle text-amber-700 ring-amber-200',
  danger: 'bg-status-danger-subtle text-red-700 ring-red-200',
  info: 'bg-status-info-subtle text-blue-700 ring-blue-200',
  neutral: 'bg-status-neutral-subtle text-ink-600 ring-ink-200',
  engineer: 'bg-engineer-100 text-engineer-700 ring-engineer-200',
  primary: 'bg-primary-100 text-primary-700 ring-primary-200',
}

const sizeClasses: Record<Size, string> = {
  sm: 'h-5 px-2 text-[11px] font-semibold tracking-wide',
  md: 'h-6 px-2.5 text-xs font-semibold',
}
</script>

<template>
  <span
    data-testid="app-badge"
    :data-variant="props.variant"
    :class="[
      'inline-flex items-center rounded-full ring-1 ring-inset uppercase',
      variantClasses[props.variant],
      sizeClasses[props.size],
    ]"
  >
    <slot />
  </span>
</template>
