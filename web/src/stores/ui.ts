import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { setLocale as setI18nLocale } from '@/i18n'

const LOCALE_KEY = 'ive.locale'
const SIDEBAR_KEY = 'ive.sidebar_collapsed'

export type Locale = 'en' | 'id'

export const useUiStore = defineStore('ui', () => {
  const initialLocale: Locale =
    typeof localStorage !== 'undefined' && localStorage.getItem(LOCALE_KEY) === 'id' ? 'id' : 'en'
  const initialCollapsed =
    typeof localStorage !== 'undefined' && localStorage.getItem(SIDEBAR_KEY) === 'true'

  const locale = ref<Locale>(initialLocale)
  const sidebarCollapsed = ref<boolean>(initialCollapsed)

  watch(sidebarCollapsed, (next) => {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(SIDEBAR_KEY, String(next))
  })

  function setLocale(next: Locale) {
    locale.value = next
    setI18nLocale(next)
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return { locale, sidebarCollapsed, setLocale, toggleSidebar }
})
