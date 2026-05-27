<script setup lang="ts">
type Step = { id: string; label: string }

const props = defineProps<{
  steps: Step[]
  current: number
}>()

function stateFor(index: number): 'done' | 'active' | 'pending' {
  if (index < props.current) return 'done'
  if (index === props.current) return 'active'
  return 'pending'
}
</script>

<template>
  <ol data-testid="app-stepper" class="flex items-center gap-3">
    <li
      v-for="(step, index) in props.steps"
      :key="step.id"
      :data-testid="`stepper-node-${step.id}`"
      :data-state="stateFor(index)"
      class="flex items-center gap-3"
    >
      <span
        :class="[
          'flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold transition-colors',
          stateFor(index) === 'done' && 'bg-primary-600 text-white',
          stateFor(index) === 'active' && 'bg-primary-50 text-primary-700 ring-2 ring-primary-500',
          stateFor(index) === 'pending' && 'bg-ink-100 text-ink-500',
        ]"
      >
        {{ index + 1 }}
      </span>
      <span
        :class="[
          'text-sm transition-colors',
          stateFor(index) === 'active' ? 'font-semibold text-ink-900' : 'text-ink-600',
        ]"
      >
        {{ step.label }}
      </span>
      <span
        v-if="index < props.steps.length - 1"
        aria-hidden="true"
        :class="[
          'h-px w-8 transition-colors',
          stateFor(index) === 'done' ? 'bg-primary-500' : 'bg-ink-200',
        ]"
      />
    </li>
  </ol>
</template>
