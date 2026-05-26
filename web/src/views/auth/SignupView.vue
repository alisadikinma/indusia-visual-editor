<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>

<template>
  <main class="min-h-screen grid place-items-center bg-ink-50 px-4">
    <div class="w-full max-w-md bg-white rounded-xl shadow-card p-8">
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('auth.signupTitle') }}</h1>
      <p class="text-sm text-ink-500 mt-2">Coming in F1 (auth wiring).</p>
      <router-link to="/login" class="text-primary-700 hover:underline mt-4 inline-block">
        {{ t('auth.haveAccount') }}
      </router-link>
    </div>
  </main>
</template>
