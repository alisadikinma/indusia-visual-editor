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
const confirm = ref('')
const orgSlug = ref('')
const mismatch = ref(false)

async function submit() {
  auth.clearError()
  mismatch.value = false
  if (password.value !== confirm.value) {
    mismatch.value = true
    return
  }
  try {
    await auth.signup(email.value, password.value, orgSlug.value || undefined)
    await router.push('/')
  } catch {
    /* error in auth.error */
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
          {{ t('auth.signupHook') }}
        </h1>
      </div>
      <ul class="space-y-3 text-sm text-white/85">
        <li>· {{ t('auth.signupBullet1') }}</li>
        <li>· {{ t('auth.signupBullet2') }}</li>
        <li>· {{ t('auth.signupBullet3') }}</li>
      </ul>
      <p class="text-xs text-white/60 font-mono">{{ t('auth.tenantNote') }}</p>
    </aside>

    <section class="flex items-center justify-center px-6 py-12">
      <form class="w-full max-w-md space-y-5" @submit.prevent="submit">
        <header class="space-y-1">
          <h2 class="text-2xl font-semibold text-ink-900">{{ t('auth.signupTitle') }}</h2>
          <p class="text-sm text-ink-500">{{ t('auth.signupSubtitle') }}</p>
        </header>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('auth.email') }}</span>
          <input
            v-model="email"
            type="email"
            autocomplete="email"
            required
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('auth.password') }}</span>
          <input
            v-model="password"
            type="password"
            autocomplete="new-password"
            required
            minlength="8"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('auth.passwordConfirm') }}</span>
          <input
            v-model="confirm"
            type="password"
            autocomplete="new-password"
            required
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>

        <label class="block space-y-1.5">
          <span class="text-sm font-medium text-ink-700">{{ t('auth.orgSlugOptional') }}</span>
          <input
            v-model="orgSlug"
            type="text"
            placeholder="default"
            class="w-full h-11 px-3 rounded-lg border border-ink-200 bg-white focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          />
        </label>

        <p
          v-if="mismatch"
          role="alert"
          class="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700"
        >
          {{ t('auth.passwordMismatch') }}
        </p>
        <p
          v-else-if="auth.error"
          role="alert"
          class="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700"
        >
          {{ auth.error }}
        </p>

        <AppButton type="submit" :disabled="auth.loading" class="w-full !h-11">
          {{ auth.loading ? t('common.loading') : t('auth.submitSignup') }}
        </AppButton>

        <p class="text-sm text-ink-500 text-center">
          {{ t('auth.haveAccount') }}
          <router-link to="/login" class="text-primary-700 hover:underline ml-1 font-medium">
            {{ t('auth.submitLogin') }}
          </router-link>
        </p>
      </form>
    </section>
  </main>
</template>
