import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import LoginView from '@/views/auth/LoginView.vue'
import { server } from '@/mocks/server'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div>dash</div>' } },
      { path: '/login', name: 'login', component: LoginView },
      { path: '/signup', name: 'signup', component: { template: '<div>signup</div>' } },
    ],
  })
}

async function mountLogin(path = '/login') {
  const router = makeRouter()
  await router.push(path)
  await router.isReady()
  const wrapper = mount(LoginView, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  return { wrapper, router }
}

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    sessionStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('renders title + tagline copy', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.text()).toContain('Sign in')
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('submits valid creds and stores token + user', async () => {
    const { wrapper, router } = await mountLogin()
    await wrapper.find('input[type="email"]').setValue('demo@indusia.example')
    await wrapper.find('input[type="password"]').setValue('any-password')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const auth = useAuthStore()
    expect(auth.accessToken).toBeTruthy()
    expect(auth.user?.email).toBe('demo@indusia.example')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('shows envelope error on 401', async () => {
    server.use(
      http.post('/api/auth/login', () =>
        HttpResponse.json(
          { status: false, message: 'invalid email or password', data: null },
          { status: 401 },
        ),
      ),
    )
    const { wrapper, router } = await mountLogin()
    await wrapper.find('input[type="email"]').setValue('demo@indusia.example')
    await wrapper.find('input[type="password"]').setValue('wrong')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('invalid email or password')
    expect(router.currentRoute.value.path).toBe('/login')
    const auth = useAuthStore()
    expect(auth.accessToken).toBeNull()
  })

  it('honors next query param on success', async () => {
    const { wrapper, router } = await mountLogin('/login?next=/projects/abc/wizard')
    await wrapper.find('input[type="email"]').setValue('demo@indusia.example')
    await wrapper.find('input[type="password"]').setValue('any-password')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/projects/abc/wizard')
  })

  // --- Figma parity (Bundle 1.1) ---

  it('renders the brand panel with stats and three workflow steps', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.find('[data-testid="login-form"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="login-brand-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('94.2%')
    expect(wrapper.findAll('[data-testid="login-workflow-step"]')).toHaveLength(3)
  })

  it('does not render a forgot-password link', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.find('[data-testid="login-forgot-password"]').exists()).toBe(false)
  })

  it('persists token to localStorage when remember-me is checked (default)', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.find('[data-testid="login-remember"]').exists()).toBe(true)
    await wrapper.find('input[type="email"]').setValue('demo@indusia.example')
    await wrapper.find('input[type="password"]').setValue('any-password')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(localStorage.getItem('ive.access_token')).toBeTruthy()
    expect(sessionStorage.getItem('ive.access_token')).toBeNull()
  })

  it('persists token to sessionStorage when remember-me is unchecked', async () => {
    const { wrapper } = await mountLogin()
    await wrapper.find('[data-testid="login-remember"]').setValue(false)
    await wrapper.find('input[type="email"]').setValue('demo@indusia.example')
    await wrapper.find('input[type="password"]').setValue('any-password')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(sessionStorage.getItem('ive.access_token')).toBeTruthy()
    expect(localStorage.getItem('ive.access_token')).toBeNull()
  })

  it('toggles dark mode via the floating theme toggle', async () => {
    const { wrapper } = await mountLogin()
    const toggle = wrapper.find('[data-testid="auth-theme-toggle"]')
    expect(toggle.exists()).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    await toggle.trigger('click')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    await toggle.trigger('click')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('switches locale via the floating language switcher', async () => {
    const { wrapper } = await mountLogin()
    await wrapper.find('[data-testid="auth-lang-id"]').trigger('click')
    expect(useUiStore().locale).toBe('id')
  })

  it('reveals the password when the show-password control is clicked', async () => {
    const { wrapper } = await mountLogin()
    const field = wrapper.find('input[type="password"]')
    expect(field.exists()).toBe(true)
    await wrapper.find('[data-testid="login-toggle-password"]').trigger('click')
    expect(wrapper.find('input[name="password"]').attributes('type')).toBe('text')
  })
})
