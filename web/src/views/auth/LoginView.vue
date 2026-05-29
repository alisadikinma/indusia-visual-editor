<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import AuthFloatingWidget from '@/components/auth/AuthFloatingWidget.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const remember = ref(true)
const showPassword = ref(false)

const workflow = [
  { n: '1', title: 'auth.step1Title', sub: 'auth.step1Sub' },
  { n: '2', title: 'auth.step2Title', sub: 'auth.step2Sub' },
  { n: '3', title: 'auth.step3Title', sub: 'auth.step3Sub' },
]

async function submit() {
  auth.clearError()
  try {
    await auth.login(email.value, password.value, remember.value)
    const next = (route.query.next as string | undefined) ?? '/'
    await router.push(next)
  } catch {
    /* error already in auth.error */
  }
}
</script>

<template>
  <main
    class="relative flex min-h-screen bg-surface-raised dark:bg-ink-950"
    data-testid="login-screen"
  >
    <AuthFloatingWidget />

    <!-- Brand panel -->
    <aside
      data-testid="login-brand-panel"
      class="hidden w-[44%] max-w-[640px] flex-col justify-between overflow-hidden bg-primary-600 p-16 text-white lg:flex"
    >
      <div class="flex items-center gap-3">
        <span
          class="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15 text-base font-bold"
          aria-hidden="true"
        >
          ◆
        </span>
        <span class="text-[17px] font-bold">Indusia Visual Editor</span>
      </div>

      <div class="flex flex-col gap-4">
        <h1 class="max-w-[512px] text-[38px] font-bold leading-[48px]">
          {{ t('auth.brandHook') }}
        </h1>
        <p class="max-w-[512px] text-base leading-[26px] text-primary-100">
          {{ t('auth.brandSub') }}
        </p>

        <div class="flex gap-10 pt-8">
          <div class="flex flex-col gap-1">
            <span class="text-[32px] font-bold leading-none">6</span>
            <span class="text-[11px] font-semibold uppercase tracking-[0.88px] text-primary-200">
              {{ t('auth.statSetupLabel') }}
            </span>
          </div>
          <div class="flex flex-col gap-1">
            <span class="text-[32px] font-bold leading-none">94.2%</span>
            <span class="text-[11px] font-semibold uppercase tracking-[0.88px] text-primary-200">
              {{ t('auth.statMapLabel') }}
            </span>
          </div>
          <div class="flex flex-col gap-1">
            <span class="text-[32px] font-bold leading-none">2</span>
            <span class="text-[11px] font-semibold uppercase tracking-[0.88px] text-primary-200">
              {{ t('auth.statGatesLabel') }}
            </span>
          </div>
        </div>

        <div class="flex flex-col gap-3 pt-1">
          <div
            v-for="step in workflow"
            :key="step.n"
            data-testid="login-workflow-step"
            class="flex items-center gap-3.5"
          >
            <span
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl border border-white bg-white/[0.18] text-sm font-bold"
            >
              {{ step.n }}
            </span>
            <div class="flex flex-col gap-0.5">
              <span class="text-sm font-semibold">{{ t(step.title) }}</span>
              <span class="text-xs text-primary-200">{{ t(step.sub) }}</span>
            </div>
          </div>
        </div>
      </div>

      <p class="text-xs text-primary-200">© 2026 Indusia AI · indusiaai@gmail.com</p>
    </aside>

    <!-- Form panel -->
    <section class="flex flex-1 items-center justify-center px-6 py-16 sm:px-24">
      <form
        data-testid="login-form"
        class="flex w-full max-w-[400px] flex-col gap-5"
        @submit.prevent="submit"
      >
        <div class="flex flex-col gap-2">
          <h2 class="text-[26px] font-bold text-text-primary dark:text-ink-50">
            {{ t('auth.loginHeading') }}
          </h2>
          <p class="text-sm text-text-secondary dark:text-ink-400">{{ t('auth.loginHint') }}</p>
        </div>

        <label class="flex flex-col gap-1.5">
          <span class="text-[13px] font-medium text-text-secondary dark:text-ink-300">
            {{ t('auth.email') }}
          </span>
          <span
            class="flex h-11 items-center gap-2.5 rounded-lg border border-border-default bg-surface-canvas px-3.5 transition focus-within:border-2 focus-within:border-border-focus dark:border-ink-700 dark:bg-ink-900"
          >
            <svg
              class="h-4 w-4 shrink-0 text-text-tertiary"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <rect x="3" y="5" width="18" height="14" rx="2" />
              <path d="m3 7 9 6 9-6" />
            </svg>
            <input
              v-model="email"
              name="email"
              type="email"
              autocomplete="email"
              required
              placeholder="admin@indusia.example.com"
              class="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary dark:text-ink-50"
            />
          </span>
        </label>

        <label class="flex flex-col gap-1.5">
          <span class="text-[13px] font-medium text-text-secondary dark:text-ink-300">
            {{ t('auth.password') }}
          </span>
          <span
            class="flex h-11 items-center gap-2.5 rounded-lg border border-border-default bg-surface-canvas px-3.5 transition focus-within:border-2 focus-within:border-border-focus dark:border-ink-700 dark:bg-ink-900"
          >
            <svg
              class="h-4 w-4 shrink-0 text-text-tertiary"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <rect x="4" y="11" width="16" height="9" rx="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
            <input
              v-model="password"
              name="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              required
              class="w-full bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary dark:text-ink-50"
            />
            <button
              data-testid="login-toggle-password"
              type="button"
              class="shrink-0 text-text-tertiary transition hover:text-text-secondary"
              :aria-label="showPassword ? t('auth.hidePassword') : t('auth.showPassword')"
              @click="showPassword = !showPassword"
            >
              <svg
                v-if="!showPassword"
                class="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg
                v-else
                class="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M9.88 5.09A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a18 18 0 0 1-3.06 3.94M6.06 6.06A18 18 0 0 0 2 12s3.5 7 10 7a10.6 10.6 0 0 0 3.06-.45" />
                <path d="m3 3 18 18" />
                <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
              </svg>
            </button>
          </span>
        </label>

        <label class="flex cursor-pointer items-center gap-2">
          <input
            v-model="remember"
            data-testid="login-remember"
            type="checkbox"
            class="h-4 w-4 rounded-sm border-border-strong text-primary-600 accent-primary-600"
          />
          <span class="text-[13px] text-text-secondary dark:text-ink-400">
            {{ t('auth.rememberMe') }}
          </span>
        </label>

        <p
          v-if="auth.error"
          role="alert"
          class="rounded-md border border-status-danger-subtle bg-status-danger-subtle px-3 py-2 text-sm text-status-danger-base"
        >
          {{ auth.error }}
        </p>

        <button
          type="submit"
          :disabled="auth.loading"
          class="flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-primary-600 text-[15px] font-semibold text-white transition hover:bg-primary-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ auth.loading ? t('common.loading') : t('auth.submitLogin') }}
          <svg
            v-if="!auth.loading"
            class="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        </button>

        <div class="flex items-center gap-3 py-1">
          <span class="h-px flex-1 bg-border-default dark:bg-ink-800" />
          <span class="text-[11px] font-semibold uppercase tracking-[0.88px] text-text-tertiary">
            {{ t('auth.orDivider') }}
          </span>
          <span class="h-px flex-1 bg-border-default dark:bg-ink-800" />
        </div>

        <p class="text-center text-[13px] text-text-secondary dark:text-ink-400">
          {{ t('auth.needAccount') }}
          <router-link
            to="/signup"
            class="ml-1 font-semibold text-primary-600 hover:underline dark:text-primary-400"
          >
            {{ t('auth.signUpHere') }}
          </router-link>
        </p>
      </form>
    </section>
  </main>
</template>
