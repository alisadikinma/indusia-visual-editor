<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import AppCard from '@/components/primitives/AppCard.vue'
import AppPill from '@/components/primitives/AppPill.vue'

const { t } = useI18n()
const ui = useUiStore()
const auth = useAuthStore()
</script>

<template>
  <div class="p-8 max-w-[800px] mx-auto space-y-6" data-testid="preferences-view">
    <header class="space-y-1">
      <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
        {{ t('preferences.kicker') }}
      </p>
      <h1 class="text-2xl font-semibold text-ink-900">{{ t('preferences.title') }}</h1>
      <p class="text-sm text-ink-500">{{ t('preferences.subhead') }}</p>
    </header>

    <AppCard padding="lg">
      <h2 class="text-base font-semibold text-ink-900 mb-4">{{ t('preferences.account') }}</h2>
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
    </AppCard>

    <AppCard padding="lg">
      <h2 class="text-base font-semibold text-ink-900 mb-3">{{ t('preferences.display') }}</h2>
      <div class="flex items-center justify-between">
        <div>
          <p class="text-sm font-medium text-ink-900">{{ t('preferences.language') }}</p>
          <p class="text-xs text-ink-500">{{ t('preferences.languageBlurb') }}</p>
        </div>
        <div
          class="inline-flex items-center rounded-full border border-border-default bg-surface-raised p-0.5 text-xs font-mono"
        >
          <AppPill
            data-testid="preferences-locale-en"
            size="sm"
            :selected="ui.locale === 'en'"
            @click="ui.setLocale('en')"
          >EN</AppPill>
          <AppPill
            data-testid="preferences-locale-id"
            size="sm"
            :selected="ui.locale === 'id'"
            @click="ui.setLocale('id')"
          >ID</AppPill>
        </div>
      </div>
      <div class="mt-4 pt-4 border-t border-border-subtle">
        <p class="text-sm font-medium text-ink-900">{{ t('preferences.engineerMode') }}</p>
        <p class="text-xs text-ink-500 mt-1">{{ t('preferences.engineerMovedHint') }}</p>
      </div>
    </AppCard>

    <p class="text-xs text-ink-500 font-mono">
      {{ t('preferences.storedLocal') }}
    </p>
  </div>
</template>
