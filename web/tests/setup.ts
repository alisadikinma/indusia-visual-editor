import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import { server } from '@/mocks/server'
import en from '@/i18n/locales/en.json'
import id from '@/i18n/locales/id.json'

const i18n = createI18n({ legacy: false, locale: 'en', messages: { en, id } })
config.global.plugins = [i18n]

beforeAll(() => {
  setActivePinia(createPinia())
  server.listen({ onUnhandledRequest: 'error' })
})

afterEach(() => {
  server.resetHandlers()
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

afterAll(() => {
  server.close()
})
