import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'

const TOKEN_KEY = 'ive.access_token'
const DISPLAY_NAME_KEY = 'ive.display_name'

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

const hasLocal = typeof localStorage !== 'undefined'
const hasSession = typeof sessionStorage !== 'undefined'

// Token storage strategy mirrors the "Remember me" choice: persistent tokens
// live in localStorage (survive browser restart), session-only tokens live in
// sessionStorage (cleared when the tab closes). Reads prefer localStorage.
function readToken(): string | null {
  if (hasLocal) {
    const t = localStorage.getItem(TOKEN_KEY)
    if (t) return t
  }
  if (hasSession) {
    const t = sessionStorage.getItem(TOKEN_KEY)
    if (t) return t
  }
  return null
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(readToken())
  const user = ref<AuthUser | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // The backend AuthUser has no name field, so the signup-form "Full name" is
  // kept client-side only (display in topbar/avatar). Persisted to localStorage
  // so it survives reloads; never sent to the API.
  const displayName = ref<string | null>(
    hasLocal ? localStorage.getItem(DISPLAY_NAME_KEY) : null,
  )

  function setDisplayName(name: string | null) {
    displayName.value = name
    if (!hasLocal) return
    if (name) localStorage.setItem(DISPLAY_NAME_KEY, name)
    else localStorage.removeItem(DISPLAY_NAME_KEY)
  }

  // 'local' (persistent across restarts) by default. Only when the existing
  // token lives solely in sessionStorage do we start in session mode — that
  // keeps setToken() without an explicit remember flag persisting to
  // localStorage, matching the long-standing store contract.
  const tokenInLocal = hasLocal && localStorage.getItem(TOKEN_KEY) !== null
  const tokenInSession = hasSession && sessionStorage.getItem(TOKEN_KEY) !== null
  const persistent = ref<boolean>(tokenInLocal || !tokenInSession)

  const isAuthenticated = computed(() => accessToken.value !== null)

  function setToken(token: string | null, remember?: boolean) {
    accessToken.value = token

    if (token === null) {
      if (hasLocal) localStorage.removeItem(TOKEN_KEY)
      if (hasSession) sessionStorage.removeItem(TOKEN_KEY)
      return
    }

    // An explicit remember flag picks the storage; otherwise keep whichever
    // storage the current session already uses (e.g. silent token refresh).
    if (remember !== undefined) persistent.value = remember

    if (persistent.value) {
      if (hasSession) sessionStorage.removeItem(TOKEN_KEY)
      if (hasLocal) localStorage.setItem(TOKEN_KEY, token)
    } else {
      if (hasLocal) localStorage.removeItem(TOKEN_KEY)
      if (hasSession) sessionStorage.setItem(TOKEN_KEY, token)
    }
  }

  function setUser(next: AuthUser | null) {
    user.value = next
  }

  async function login(email: string, password: string, remember = true): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const data = await authApi.login(email, password)
      setToken(data.access_token, remember)
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
      setToken(data.access_token, true)
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
    setDisplayName(null)
  }

  function clearError() {
    error.value = null
  }

  return {
    accessToken,
    user,
    displayName,
    loading,
    error,
    isAuthenticated,
    setToken,
    setUser,
    setDisplayName,
    login,
    signup,
    loadCurrentUser,
    logout,
    clearError,
  }
})
