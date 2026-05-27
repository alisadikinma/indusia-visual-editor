<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'
import { useEngineerStore } from '@/stores/engineer'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const ui = useUiStore()
const engineer = useEngineerStore()
const auth = useAuthStore()
</script>

<template>
  <div class="p-8 max-w-[800px] mx-auto space-y-6">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('preferences.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('preferences.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('preferences.subhead') }}</p>
    </header>

    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5 space-y-4">
      <h2 class="text-base font-semibold text-ink-900">{{ t('preferences.account') }}</h2>
      <dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">Email</dt>
          <dd class="font-medium text-ink-900">{{ auth.user?.email ?? '—' }}</dd>
        </div>
        <div>
          <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('preferences.role') }}</dt>
          <dd class="font-mono text-ink-900">{{ auth.user?.role ?? '—' }}</dd>
        </div>
        <div class="col-span-2">
          <dt class="text-xs font-mono uppercase tracking-wider text-ink-500">{{ t('preferences.org') }}</dt>
          <dd class="font-mono text-xs text-ink-700">{{ auth.user?.organization_id ?? '—' }}</dd>
        </div>
      </dl>
    </section>

    <section class="rounded-xl bg-white border border-ink-200 shadow-card p-5 space-y-3">
      <h2 class="text-base font-semibold text-ink-900">{{ t('preferences.display') }}</h2>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium text-ink-900">{{ t('preferences.language') }}</p>
          <p class="text-xs text-ink-500">{{ t('preferences.languageBlurb') }}</p>
        </div>
        <div class="inline-flex items-center rounded-full border border-ink-200 bg-ink-50 p-0.5 text-xs font-mono">
          <button
            type="button"
            class="h-7 px-3 rounded-full transition"
            :class="ui.locale === 'en' ? 'bg-white text-ink-900 shadow-card' : 'text-ink-500'"
            @click="ui.setLocale('en')"
          >
            EN
          </button>
          <button
            type="button"
            class="h-7 px-3 rounded-full transition"
            :class="ui.locale === 'id' ? 'bg-white text-ink-900 shadow-card' : 'text-ink-500'"
            @click="ui.setLocale('id')"
          >
            ID
          </button>
        </div>
      </div>
      <div class="flex items-center justify-between border-t border-ink-100 pt-3">
        <div>
          <p class="text-sm font-medium text-ink-900">{{ t('preferences.engineerMode') }}</p>
          <p class="text-xs text-ink-500">{{ t('preferences.engineerBlurb') }}</p>
        </div>
        <button
          type="button"
          class="inline-flex h-6 w-11 rounded-full p-0.5 transition"
          :class="engineer.enabled ? 'bg-engineer-700' : 'bg-ink-300'"
          :aria-pressed="engineer.enabled"
          @click="engineer.toggle()"
        >
          <span
            class="h-5 w-5 rounded-full bg-white transition-transform"
            :class="engineer.enabled ? 'translate-x-5' : ''"
          />
        </button>
      </div>
    </section>

    <p class="text-xs text-ink-500 font-mono">
      {{ t('preferences.storedLocal') }}
    </p>
  </div>
</template>
