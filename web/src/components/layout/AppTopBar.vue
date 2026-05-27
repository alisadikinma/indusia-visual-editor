<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useEngineerStore } from '@/stores/engineer'
import AppPill from '@/components/primitives/AppPill.vue'
import IconButton from '@/components/primitives/IconButton.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const engineer = useEngineerStore()

const pageTitle = computed(() => {
  const key = (route.meta?.titleKey as string | undefined) ?? `nav.${String(route.name ?? '')}`
  return t(key, t('nav.dashboard'))
})

async function doLogout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <header
    data-testid="app-topbar"
    class="h-16 bg-surface-canvas border-b border-border-default flex items-center justify-between px-6 gap-4"
  >
    <div class="flex items-center gap-3 min-w-0">
      <IconButton
        data-testid="topbar-sidebar-toggle"
        variant="ghost"
        size="sm"
        :aria-label="t('common.toggleSidebar')"
        @click="ui.toggleSidebar()"
      >
        <span class="block h-4 w-4 rounded-sm border-2 border-current" />
      </IconButton>
      <nav
        data-testid="topbar-breadcrumb"
        class="flex items-center gap-2 text-sm text-ink-500 min-w-0"
      >
        <span class="font-mono text-xs uppercase tracking-wider text-ink-400">
          {{ t('app.shortName') }}
        </span>
        <span aria-hidden="true">/</span>
        <span class="font-medium text-ink-900 truncate">{{ pageTitle }}</span>
      </nav>
    </div>

    <div class="flex items-center gap-2">
      <div
        class="inline-flex items-center rounded-full border border-border-default bg-surface-raised p-0.5 text-xs font-mono"
      >
        <AppPill
          data-testid="topbar-locale-en"
          size="sm"
          :selected="ui.locale === 'en'"
          @click="ui.setLocale('en')"
        >
          EN
        </AppPill>
        <AppPill
          data-testid="topbar-locale-id"
          size="sm"
          :selected="ui.locale === 'id'"
          @click="ui.setLocale('id')"
        >
          ID
        </AppPill>
      </div>

      <button
        data-testid="topbar-engineer-toggle"
        type="button"
        class="inline-flex items-center gap-2 h-8 px-3 rounded-full border text-xs font-mono transition"
        :class="
          engineer.enabled
            ? 'border-engineer-200 bg-engineer-50 text-engineer-800'
            : 'border-border-default bg-surface-canvas text-ink-500 hover:text-ink-700'
        "
        :aria-pressed="engineer.enabled"
        @click="engineer.toggle()"
      >
        <span class="opacity-80">&lt;/&gt;</span>
        {{ t('engineer.toggle') }}
        <span
          class="ml-1 inline-flex h-4 w-7 rounded-full p-0.5 transition"
          :class="engineer.enabled ? 'bg-engineer-700' : 'bg-ink-300'"
        >
          <span
            class="h-3 w-3 rounded-full bg-white transition-transform"
            :class="engineer.enabled ? 'translate-x-3' : ''"
          />
        </span>
      </button>

      <div class="h-6 w-px bg-border-default mx-1" />

      <div class="flex items-center gap-3">
        <div class="text-right leading-tight hidden sm:block">
          <div class="text-xs font-medium text-ink-900 truncate max-w-[160px]">
            {{ auth.user?.email ?? '—' }}
          </div>
          <div class="text-[11px] font-mono uppercase tracking-wider text-ink-500">
            {{ auth.user?.role ?? '' }}
          </div>
        </div>
        <button
          data-testid="topbar-logout"
          type="button"
          class="h-8 px-3 rounded-md text-xs font-medium text-ink-500 hover:text-ink-900 hover:bg-ink-100 transition"
          @click="doLogout"
        >
          {{ t('nav.logout') }}
        </button>
      </div>
    </div>
  </header>
</template>
