<script setup lang="ts">
type Variant = 'default' | 'raised' | 'sunken' | 'emerald' | 'engineer'
type Padding = 'none' | 'sm' | 'md' | 'lg'

const props = withDefaults(
  defineProps<{
    variant?: Variant
    padding?: Padding
  }>(),
  { variant: 'default', padding: 'md' },
)

const variantClasses: Record<Variant, string> = {
  default: 'bg-surface-canvas border-border-default',
  raised: 'bg-surface-raised border-border-subtle',
  sunken: 'bg-surface-sunken border-border-subtle',
  emerald: 'bg-primary-50 border-primary-200',
  engineer: 'bg-engineer-50 border-engineer-200',
}

const paddingClasses: Record<Padding, string> = {
  none: 'p-0',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
}
</script>

<template>
  <section
    data-testid="app-card"
    :data-variant="props.variant"
    :class="[
      'rounded-xl border shadow-card transition-colors',
      variantClasses[props.variant],
      paddingClasses[props.padding],
    ]"
  >
    <slot />
  </section>
</template>
