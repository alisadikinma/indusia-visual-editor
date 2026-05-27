import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'

const TOKEN_KEY = 'ive.access_token'

export interface AuthUser {
  id: string
  email: string
  role: 'admin' | 'engineer' | 'viewer'
  organization_id: string
}

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null,
  )
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => accessToken.value !== null)

  function setToken(token: string | null) {
    accessToken.value = token
    if (typeof localStorage === 'undefined') return
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  }

  function setUser(next: AuthUser | null) {
    user.value = next
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await authApi.login(email, password)
      setToken(data.access_token)
      setUser(data.user)
    } catch (err) {
      error.value = extractMessage(err, 'Login failed')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function signup(
    email: string,
    password: string,
    organizationSlug?: string,
  ): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await authApi.signup(email, password, organizationSlug)
      setToken(data.access_token)
      setUser(data.user)
    } catch (err) {
      error.value = extractMessage(err, 'Signup failed')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadCurrentUser(): Promise<void> {
    if (!accessToken.value) return
    try {
      const u = await authApi.me()
      setUser(u)
    } catch {
      setToken(null)
      setUser(null)
    }
  }

  async function logout(): Promise<void> {
    await authApi.logout()
    setToken(null)
    setUser(null)
  }

  function clearError() {
    error.value = null
  }

  return {
    accessToken,
    user,
    loading,
    error,
    isAuthenticated,
    setToken,
    setUser,
    login,
    signup,
    loadCurrentUser,
    logout,
    clearError,
  }
})
