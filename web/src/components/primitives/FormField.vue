<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    id: string
    label: string
    hint?: string
    error?: string
    required?: boolean
  }>(),
  { required: false },
)

const invalid = () => Boolean(props.error)
</script>

<template>
  <div
    data-testid="form-field"
    :data-invalid="invalid() ? 'true' : 'false'"
    class="flex flex-col gap-1.5"
  >
    <label
      :for="props.id"
      class="text-sm font-medium text-ink-800"
    >
      {{ props.label }}
      <span v-if="props.required" aria-hidden="true" class="text-red-500">*</span>
    </label>
    <slot />
    <p
      v-if="props.error"
      :id="`${props.id}-error`"
      role="alert"
      class="text-xs text-red-600"
    >
      {{ props.error }}
    </p>
    <p
      v-else-if="props.hint"
      :id="`${props.id}-hint`"
      class="text-xs text-ink-500"
    >
      {{ props.hint }}
    </p>
  </div>
</template>
