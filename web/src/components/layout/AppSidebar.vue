<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUiStore } from '@/stores/ui'

interface NavItem {
  to?: string
  labelKey: string
  icon: string
  disabled?: boolean
}

const { t } = useI18n()
const route = useRoute()
const ui = useUiStore()

const workspaceItems = computed<NavItem[]>(() => [
  { to: '/', labelKey: 'nav.dashboard', icon: 'grid' },
  { labelKey: 'nav.labeling', icon: 'square-mouse-pointer', disabled: true },
  { labelKey: 'nav.training', icon: 'cpu', disabled: true },
  { labelKey: 'nav.eval', icon: 'gauge', disabled: true },
])

const settingsItems = computed<NavItem[]>(() => [
  { labelKey: 'nav.models', icon: 'box', disabled: true },
  { labelKey: 'nav.edges', icon: 'server', disabled: true },
  { labelKey: 'nav.datasets', icon: 'database', disabled: true },
  { labelKey: 'nav.team', icon: 'users', disabled: true },
  { labelKey: 'nav.preferences', icon: 'settings', disabled: true },
])

function isActive(to?: string) {
  if (!to) return false
  return route.path === to || (to !== '/' && route.path.startsWith(to))
}
</script>

<template>
  <aside
    class="flex flex-col bg-white border-r border-ink-200 transition-all duration-200"
    :class="ui.sidebarCollapsed ? 'w-16' : 'w-60'"
  >
    <div
      class="flex items-center gap-3 h-16 px-4 border-b border-ink-200"
      :class="ui.sidebarCollapsed ? 'justify-center' : ''"
    >
      <div
        class="h-9 w-9 rounded-lg bg-primary-700 grid place-items-center text-white font-mono text-sm font-semibold shrink-0"
      >
        IV
      </div>
      <div v-if="!ui.sidebarCollapsed" class="leading-tight">
        <div class="text-sm font-semibold text-ink-900">Indusia</div>
        <div class="text-xs text-ink-500">{{ t('app.shortName') }}</div>
      </div>
    </div>

    <nav class="flex-1 overflow-y-auto py-4 px-2 space-y-6">
      <div>
        <p
          v-if="!ui.sidebarCollapsed"
          class="px-3 mb-2 text-[11px] font-mono uppercase tracking-wider text-ink-400"
        >
          {{ t('nav.sectionWorkspace') }}
        </p>
        <ul class="space-y-1">
          <li v-for="item in workspaceItems" :key="item.labelKey">
            <router-link
              v-if="item.to && !item.disabled"
              :to="item.to"
              class="flex items-center gap-3 h-9 px-3 rounded-md text-sm font-medium transition"
              :class="
                isActive(item.to)
                  ? 'bg-primary-50 text-primary-800'
                  : 'text-ink-700 hover:bg-ink-100'
              "
              :title="t(item.labelKey)"
            >
              <span class="h-4 w-4 shrink-0 rounded-sm bg-current opacity-70" />
              <span v-if="!ui.sidebarCollapsed">{{ t(item.labelKey) }}</span>
            </router-link>
            <div
              v-else
              class="flex items-center gap-3 h-9 px-3 rounded-md text-sm font-medium text-ink-400 cursor-not-allowed"
              :title="t('common.comingSoon')"
            >
              <span class="h-4 w-4 shrink-0 rounded-sm bg-current opacity-50" />
              <span v-if="!ui.sidebarCollapsed">{{ t(item.labelKey) }}</span>
            </div>
          </li>
        </ul>
      </div>

      <div>
        <p
          v-if="!ui.sidebarCollapsed"
          class="px-3 mb-2 text-[11px] font-mono uppercase tracking-wider text-ink-400"
        >
          {{ t('nav.sectionSettings') }}
        </p>
        <ul class="space-y-1">
          <li v-for="item in settingsItems" :key="item.labelKey">
            <div
              class="flex items-center gap-3 h-9 px-3 rounded-md text-sm font-medium text-ink-400 cursor-not-allowed"
              :title="t('common.comingSoon')"
            >
              <span class="h-4 w-4 shrink-0 rounded-sm bg-current opacity-50" />
              <span v-if="!ui.sidebarCollapsed">{{ t(item.labelKey) }}</span>
            </div>
          </li>
        </ul>
      </div>
    </nav>

    <div class="border-t border-ink-200 p-3">
      <div
        class="flex items-center gap-3"
        :class="ui.sidebarCollapsed ? 'justify-center' : ''"
      >
        <div
          class="h-9 w-9 rounded-full bg-engineer-100 border border-engineer-200 grid place-items-center text-engineer-700 font-mono text-xs font-semibold shrink-0"
        >
          AI
        </div>
        <div v-if="!ui.sidebarCollapsed" class="leading-tight">
          <div class="text-xs font-medium text-ink-700">{{ t('app.aiAdvisor') }}</div>
          <div class="text-[11px] text-ink-500">Gemma 4 · 31b</div>
        </div>
      </div>
    </div>
  </aside>
</template>
