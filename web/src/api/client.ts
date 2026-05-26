import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/auth'

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 30_000,
})

apiClient.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken && config.headers) {
    config.headers.Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as RetriableConfig | undefined
    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !original.url?.includes('/auth/')
    ) {
      original._retried = true
      try {
        const refresh = await axios.post('/api/auth/refresh', null, { withCredentials: true })
        const token = refresh.data?.data?.access_token
        if (token) {
          const auth = useAuthStore()
          auth.setToken(token)
          if (original.headers) {
            original.headers.Authorization = `Bearer ${token}`
          }
          return apiClient(original)
        }
      } catch {
        const auth = useAuthStore()
        auth.logout()
      }
    }
    return Promise.reject(error)
  },
)
