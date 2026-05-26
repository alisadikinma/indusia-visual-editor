<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const loading = ref(false)

async function submit() {
  loading.value = true
  error.value = null
  try {
    auth.setToken('mock-access-token')
    auth.setUser({
      id: '00000000-0000-0000-0000-000000000001',
      email: email.value || 'demo@indusia.example',
      role: 'admin',
      organization_id: '00000000-0000-0000-0000-000000000001',
    })
    await router.push({ name: 'dashboard' })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="min-h-screen grid place-items-center bg-ink-50 px-4">
    <form
      class="w-full max-w-md bg-white rounded-xl shadow-card p-8 space-y-5"
      @submit.prevent="submit"
    >
      <header class="space-y-1">
        <h1 class="text-2xl font-semibold text-ink-900">{{ t('auth.loginTitle') }}</h1>
        <p class="text-sm text-ink-500">{{ t('app.tagline') }}</p>
      </header>

      <label class="block space-y-1">
        <span class="text-sm font-medium text-ink-700">{{ t('auth.email') }}</span>
        <input
          v-model="email"
          type="email"
          autocomplete="email"
          required
          class="w-full h-10 px-3 rounded-md border border-ink-200 focus:border-primary-600 outline-none"
        />
      </label>

      <label class="block space-y-1">
        <span class="text-sm font-medium text-ink-700">{{ t('auth.password') }}</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          class="w-full h-10 px-3 rounded-md border border-ink-200 focus:border-primary-600 outline-none"
        />
      </label>

      <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

      <AppButton type="submit" :disabled="loading" class="w-full">
        {{ loading ? t('common.loading') : t('auth.submitLogin') }}
      </AppButton>

      <p class="text-sm text-ink-500 text-center">
        {{ t('auth.needAccount') }}
        <router-link to="/signup" class="text-primary-700 hover:underline ml-1">
          {{ t('auth.submitSignup') }}
        </router-link>
      </p>
    </form>
  </main>
</template>
