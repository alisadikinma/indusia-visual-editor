import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const TOKEN_KEY = 'ive.access_token'

export interface AuthUser {
  id: string
  email: string
  role: 'admin' | 'engineer' | 'viewer'
  organization_id: string
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(
    typeof localStorage !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null,
  )
  const user = ref<AuthUser | null>(null)

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

  function logout() {
    setToken(null)
    setUser(null)
  }

  return {
    accessToken,
    user,
    isAuthenticated,
    setToken,
    setUser,
    logout,
  }
})
