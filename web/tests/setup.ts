import { afterAll, afterEach, beforeAll, vi } from 'vitest'
import { config } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createPinia, setActivePinia } from 'pinia'
import { server } from '@/mocks/server'
import en from '@/i18n/locales/en.json'
import id from '@/i18n/locales/id.json'

// happy-dom (node 22) does not expose bare `localStorage` / `sessionStorage`
// globals, so provide a real in-memory Storage implementation. Store-level
// specs (auth/engineer) still vi.stubGlobal their own localStorage on top of
// this; Vitest isolates globals per file so there is no cross-file leakage.
class MemoryStorage implements Storage {
  private m = new Map<string, string>()
  get length(): number {
    return this.m.size
  }
  key(index: number): string | null {
    return Array.from(this.m.keys())[index] ?? null
  }
  getItem(key: string): string | null {
    return this.m.get(key) ?? null
  }
  setItem(key: string, value: string): void {
    this.m.set(String(key), String(value))
  }
  removeItem(key: string): void {
    this.m.delete(key)
  }
  clear(): void {
    this.m.clear()
  }
}

const localStorageImpl = new MemoryStorage()
const sessionStorageImpl = new MemoryStorage()
globalThis.localStorage = localStorageImpl
globalThis.sessionStorage = sessionStorageImpl

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
  localStorageImpl.clear()
  sessionStorageImpl.clear()
})

afterAll(() => {
  server.close()
})
