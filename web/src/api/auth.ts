import { apiClient } from './client'
import type { AuthUser } from '@/stores/auth'

export interface LoginResponseData {
  access_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function login(email: string, password: string): Promise<LoginResponseData> {
  const { data } = await apiClient.post<Envelope<LoginResponseData>>('/auth/login', {
    email,
    password,
  })
  return data.data
}

export async function signup(
  email: string,
  password: string,
  organizationSlug?: string,
): Promise<LoginResponseData> {
  const { data } = await apiClient.post<Envelope<LoginResponseData>>('/auth/signup', {
    email,
    password,
    ...(organizationSlug ? { organization_slug: organizationSlug } : {}),
  })
  return data.data
}

export async function refresh(): Promise<{ access_token: string }> {
  const { data } = await apiClient.post<Envelope<{ access_token: string }>>(
    '/auth/refresh',
    null,
  )
  return data.data
}

export async function me(): Promise<AuthUser> {
  const { data } = await apiClient.get<Envelope<AuthUser>>('/auth/me')
  return data.data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout', null).catch(() => undefined)
}
