<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<template>
  <main class="min-h-screen bg-ink-50 p-8">
    <h1 class="text-2xl font-semibold text-ink-900">{{ t('nav.gate1') }}</h1>
    <p class="text-sm text-ink-500 mt-2">Gate 1 preview — implemented in F4.</p>
  </main>
</template>
