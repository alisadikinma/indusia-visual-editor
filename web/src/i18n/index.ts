import { createI18n } from 'vue-i18n'
import en from './locales/en.json'
import id from './locales/id.json'

const STORAGE_KEY = 'ive.locale'

function detectLocale(): 'en' | 'id' {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null
  if (stored === 'en' || stored === 'id') return stored
  return 'en'
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages: { en, id },
})

export function setLocale(locale: 'en' | 'id') {
  i18n.global.locale.value = locale
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(STORAGE_KEY, locale)
  }
}
