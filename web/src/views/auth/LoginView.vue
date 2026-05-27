<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppButton from '@/components/primitives/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')

async function submit() {
  auth.clearError()
  try {
    await auth.login(email.value, password.value)
    const next = (route.query.next as string | undefined) ?? '/'
    await router.push(next)
  } catch {
    /* error already in auth.error */
  }
}
</script>

<template>
  <main class="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-ink-50">
    <aside
      class="hidden md:flex flex-col justify-between p-12 bg-gradient-to-br from-primary-700 to-primary-800 text-white"
    >
      <div>
        <div class="text-sm font-mono tracking-wider opacity-80">INDUSIA</div>
        <h1 class="mt-2 text-3xl font-semibold leading-tight">
          {{ t('auth.brandHook') }}
        </h1>
      </div>
      <ul class="space-y-3 text-sm text-white/85">
        <li>· {{ t('auth.bullet1') }}</li>
        <li>· {{ t('auth.bullet2') }}</li>
        <li>· {{ t('auth.bullet3') }}</li>
      </ul>
      <p class="text-xs text-white/60 font-mono">v0.2.0 · {{ t('auth.tenantNote') }}</p>
    </aside>

    <section class="flex items-center justify-center px-6 py-12">
      <form class="w-full max-w-md space-y-6" @submit.prevent="submit">
        <header class="space-y-1">
          <h2 class="text-2xl font-semibold text-ink-900">{{ t('auth.loginTitle') }}</h2>
          <p class="text-sm text-ink-500">{{ t('auth.loginSubtitle') }}</p>
        </header>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('auth.email') }}</span>
          <input
            v-model="email"
            type="email"
            autocomplete="email"
            required
            placeholder="anda@perusahaan.com"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('auth.password') }}</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>

        <p
          v-if="auth.error"
          role="alert"
          class="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700"
        >
          {{ auth.error }}
        </p>

        <AppButton type="submit" :disabled="auth.loading" class="w-full !h-11">
          {{ auth.loading ? t('common.loading') : t('auth.submitLogin') }}
        </AppButton>

        <p class="text-sm text-ink-500 text-center">
          {{ t('auth.needAccount') }}
          <router-link to="/signup" class="text-primary-700 hover:underline ml-1 font-medium">
            {{ t('auth.submitSignup') }}
          </router-link>
        </p>
      </form>
    </section>
  </main>
</template>
