<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const ui = useUiStore()
</script>

<template>
  <div class="absolute right-6 top-6 z-10 flex items-center gap-2">
    <div
      class="flex h-9 items-center rounded-lg border border-border-subtle bg-surface-sunken p-[3px] dark:border-ink-700 dark:bg-ink-800"
    >
      <button
        data-testid="auth-lang-en"
        type="button"
        class="h-[30px] w-[41px] rounded-md text-[11px] font-semibold transition"
        :class="
          ui.locale === 'en'
            ? 'border border-border-subtle bg-surface-canvas text-text-primary dark:border-ink-600 dark:bg-ink-700 dark:text-ink-50'
            : 'text-text-tertiary hover:text-text-secondary'
        "
        @click="ui.setLocale('en')"
      >
        EN
      </button>
      <button
        data-testid="auth-lang-id"
        type="button"
        class="h-[30px] w-[41px] rounded-md text-[11px] font-semibold transition"
        :class="
          ui.locale === 'id'
            ? 'border border-border-subtle bg-surface-canvas text-text-primary dark:border-ink-600 dark:bg-ink-700 dark:text-ink-50'
            : 'text-text-tertiary hover:text-text-secondary'
        "
        @click="ui.setLocale('id')"
      >
        ID
      </button>
    </div>

    <button
      data-testid="auth-theme-toggle"
      type="button"
      class="flex h-9 w-9 items-center justify-center rounded-lg border border-border-default bg-surface-canvas text-text-secondary transition hover:text-text-primary dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200"
      :aria-label="t('auth.themeToggle')"
      @click="ui.toggleTheme()"
    >
      <svg
        v-if="ui.theme === 'light'"
        class="h-4 w-4"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" />
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
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
      </svg>
    </button>
  </div>
</template>
