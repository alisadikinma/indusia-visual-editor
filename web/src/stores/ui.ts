import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { setLocale as setI18nLocale } from '@/i18n'

const LOCALE_KEY = 'ive.locale'
const SIDEBAR_KEY = 'ive.sidebar_collapsed'
const THEME_KEY = 'ive.theme'

export type Locale = 'en' | 'id'
export type Theme = 'light' | 'dark'

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export const useUiStore = defineStore('ui', () => {
  const hasStorage = typeof localStorage !== 'undefined'

  const initialLocale: Locale =
    hasStorage && localStorage.getItem(LOCALE_KEY) === 'id' ? 'id' : 'en'
  const initialCollapsed = hasStorage && localStorage.getItem(SIDEBAR_KEY) === 'true'
  const initialTheme: Theme =
    hasStorage && localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'

  const locale = ref<Locale>(initialLocale)
  const sidebarCollapsed = ref<boolean>(initialCollapsed)
  const theme = ref<Theme>(initialTheme)

  // Reflect the persisted theme onto <html> as soon as the store mounts.
  applyTheme(theme.value)

  watch(sidebarCollapsed, (next) => {
    if (!hasStorage) return
    localStorage.setItem(SIDEBAR_KEY, String(next))
  })

  watch(theme, (next) => {
    applyTheme(next)
    if (!hasStorage) return
    localStorage.setItem(THEME_KEY, next)
  })

  function setLocale(next: Locale) {
    locale.value = next
    setI18nLocale(next)
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setTheme(next: Theme) {
    theme.value = next
  }

  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  return {
    locale,
    sidebarCollapsed,
    theme,
    setLocale,
    toggleSidebar,
    setTheme,
    toggleTheme,
  }
})
