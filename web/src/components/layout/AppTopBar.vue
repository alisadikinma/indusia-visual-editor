<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useEngineerStore } from '@/stores/engineer'

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
    class="h-16 bg-white border-b border-ink-200 flex items-center justify-between px-6 gap-4"
  >
    <div class="flex items-center gap-3 min-w-0">
      <button
        type="button"
        class="h-8 w-8 grid place-items-center rounded-md text-ink-500 hover:bg-ink-100"
        :aria-label="t('common.toggleSidebar')"
        @click="ui.toggleSidebar()"
      >
        <span class="block h-4 w-4 rounded-sm border-2 border-current" />
      </button>
      <nav class="flex items-center gap-2 text-sm text-ink-500 min-w-0">
        <span class="font-mono text-xs uppercase tracking-wider text-ink-400">
          {{ t('app.shortName') }}
        </span>
        <span aria-hidden="true">/</span>
        <span class="font-medium text-ink-900 truncate">{{ pageTitle }}</span>
      </nav>
    </div>

    <div class="flex items-center gap-2">
      <div
        class="inline-flex items-center rounded-full border border-ink-200 bg-ink-50 p-0.5 text-xs font-mono"
      >
        <button
          type="button"
          class="h-7 px-3 rounded-full transition"
          :class="
            ui.locale === 'en' ? 'bg-white text-ink-900 shadow-card' : 'text-ink-500'
          "
          @click="ui.setLocale('en')"
        >
          EN
        </button>
        <button
          type="button"
          class="h-7 px-3 rounded-full transition"
          :class="
            ui.locale === 'id' ? 'bg-white text-ink-900 shadow-card' : 'text-ink-500'
          "
          @click="ui.setLocale('id')"
        >
          ID
        </button>
      </div>

      <button
        type="button"
        class="inline-flex items-center gap-2 h-8 px-3 rounded-full border text-xs font-mono transition"
        :class="
          engineer.enabled
            ? 'border-engineer-200 bg-engineer-50 text-engineer-800'
            : 'border-ink-200 bg-white text-ink-500 hover:text-ink-700'
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

      <div class="h-6 w-px bg-ink-200 mx-1" />

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
