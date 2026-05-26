import { describe, expect, it, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('starts unauthenticated', () => {
    const auth = useAuthStore()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.accessToken).toBeNull()
  })

  it('persists token via setToken', () => {
    const auth = useAuthStore()
    auth.setToken('abc')
    expect(auth.isAuthenticated).toBe(true)
    expect(localStorage.getItem('ive.access_token')).toBe('abc')
  })

  it('clears token + user on logout', () => {
    const auth = useAuthStore()
    auth.setToken('abc')
    auth.setUser({
      id: '1',
      email: 'a@b.c',
      role: 'admin',
      organization_id: 'org',
    })
    auth.logout()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.user).toBeNull()
    expect(localStorage.getItem('ive.access_token')).toBeNull()
  })
})
