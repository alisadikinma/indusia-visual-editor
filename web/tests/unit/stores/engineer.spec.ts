import { describe, expect, it, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useEngineerStore } from '@/stores/engineer'

describe('engineer store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('starts disabled', () => {
    const store = useEngineerStore()
    expect(store.enabled).toBe(false)
  })

  it('toggles + persists to localStorage', async () => {
    const store = useEngineerStore()
    store.toggle()
    await new Promise((r) => setTimeout(r, 0))
    expect(store.enabled).toBe(true)
    expect(localStorage.getItem('ive.engineer_mode')).toBe('true')
  })
})
