<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useEngineerStore } from '@/stores/engineer'

const { t } = useI18n()
const ui = useUiStore()
const auth = useAuthStore()
const engineer = useEngineerStore()

const themes: { key: 'light' | 'dark'; labelKey: string }[] = [
  { key: 'light', labelKey: 'preferences.themeLight' },
  { key: 'dark', labelKey: 'preferences.themeDark' },
]
</script>

<template>
  <div class="p-8 max-w-[900px] mx-auto space-y-6" data-testid="preferences-view">
    <header>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('preferences.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('preferences.subhead') }}</p>
    </header>

    <!-- Profile (read-only) -->
    <section class="rounded-xl bg-white border border-border-default shadow-card p-6">
      <h2 class="text-base font-semibold text-ink-900">{{ t('preferences.account') }}</h2>
      <p class="text-sm text-ink-500 mb-4">{{ t('preferences.accountSub') }}</p>
      <dl class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div>
          <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">Email</dt>
          <dd class="font-medium text-ink-900">{{ auth.user?.email ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('preferences.role') }}</dt>
          <dd class="font-mono text-ink-900">{{ auth.user?.role ?? '—' }}</dd>
        </div>
        <div class="sm:col-span-2">
          <dt class="text-[11px] font-mono uppercase tracking-wider text-ink-500">{{ t('preferences.org') }}</dt>
          <dd class="font-mono text-xs text-ink-700">{{ auth.user?.organization_id ?? '—' }}</dd>
        </div>
      </dl>
    </section>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
      <!-- Language -->
      <section class="rounded-xl bg-white border border-border-default shadow-card p-6">
        <h2 class="text-base font-semibold text-ink-900">{{ t('preferences.language') }}</h2>
        <p class="text-sm text-ink-500 mb-3">{{ t('preferences.languageBlurb') }}</p>
        <div class="space-y-2">
          <label
            v-for="lang in (['id', 'en'] as const)"
            :key="lang"
            class="flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition"
            :class="ui.locale === lang ? 'border-primary-400 bg-primary-50' : 'border-border-default hover:bg-ink-50'"
          >
            <input
              :data-testid="`preferences-locale-${lang}`"
              type="radio"
              :value="lang"
              :checked="ui.locale === lang"
              class="accent-primary-600"
              @change="ui.setLocale(lang)"
            />
            <span class="text-sm font-medium text-ink-900">{{ t(`preferences.lang.${lang}`) }}</span>
          </label>
        </div>
      </section>

      <!-- Theme -->
      <section class="rounded-xl bg-white border border-border-default shadow-card p-6">
        <h2 class="text-base font-semibold text-ink-900">{{ t('preferences.theme') }}</h2>
        <p class="text-sm text-ink-500 mb-3">{{ t('preferences.themeBlurb') }}</p>
        <div class="grid grid-cols-2 gap-3">
          <button
            v-for="th in themes"
            :key="th.key"
            type="button"
            :data-testid="`preferences-theme-${th.key}`"
            class="rounded-lg border-2 p-3 text-sm font-medium transition"
            :class="ui.theme === th.key ? 'border-primary-400 bg-primary-50 text-primary-800' : 'border-border-default text-ink-700 hover:bg-ink-50'"
            @click="ui.setTheme(th.key)"
          >
            {{ t(th.labelKey) }}
          </button>
        </div>
      </section>
    </div>

    <!-- Engineer mode -->
    <section class="rounded-xl bg-white border border-border-default shadow-card p-6">
      <div class="flex items-center justify-between gap-4">
        <div>
          <h2 class="text-base font-semibold text-ink-900">{{ t('preferences.engineerMode') }}</h2>
          <p class="text-sm text-ink-500">{{ t('preferences.engineerBlurb') }}</p>
        </div>
        <button
          type="button"
          data-testid="preferences-engineer-toggle"
          class="inline-flex h-6 w-11 rounded-full p-0.5 transition shrink-0"
          :class="engineer.enabled ? 'bg-engineer-600' : 'bg-ink-300'"
          :aria-pressed="engineer.enabled"
          @click="engineer.toggle()"
        >
          <span class="h-5 w-5 rounded-full bg-white transition-transform" :class="engineer.enabled ? 'translate-x-5' : ''" />
        </button>
      </div>
    </section>

    <p class="text-xs text-ink-500 font-mono">{{ t('preferences.storedLocal') }}</p>
  </div>
</template>
