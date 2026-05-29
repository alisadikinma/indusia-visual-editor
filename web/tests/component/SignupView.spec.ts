import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import SignupView from '@/views/auth/SignupView.vue'
import { server } from '@/mocks/server'
import { useAuthStore } from '@/stores/auth'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div>dash</div>' } },
      { path: '/signup', name: 'signup', component: SignupView },
      { path: '/login', name: 'login', component: { template: '<div>login</div>' } },
    ],
  })
}

async function mountSignup() {
  const router = makeRouter()
  await router.push('/signup')
  await router.isReady()
  const wrapper = mount(SignupView, { global: { plugins: [router] }, attachTo: document.body })
  return { wrapper, router }
}

async function fillValid(wrapper: Awaited<ReturnType<typeof mountSignup>>['wrapper']) {
  await wrapper.find('input[name="fullName"]').setValue('Ali Sadikin')
  await wrapper.find('input[type="email"]').setValue('new@indusia.example')
  const pw = wrapper.findAll('input[name="password"], input[name="confirm"]')
  await wrapper.find('input[name="password"]').setValue('strongpassword')
  await wrapper.find('input[name="confirm"]').setValue('strongpassword')
  void pw
}

describe('SignupView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    sessionStorage.clear()
    document.documentElement.classList.remove('dark')
  })

  it('renders heading + form fields', async () => {
    const { wrapper } = await mountSignup()
    expect(wrapper.text()).toContain('Create a new account')
    expect(wrapper.find('input[name="fullName"]').exists()).toBe(true)
    expect(wrapper.find('input[type="email"]').exists()).toBe(true)
    expect(wrapper.find('input[name="password"]').exists()).toBe(true)
    expect(wrapper.find('input[name="confirm"]').exists()).toBe(true)
  })

  it('renders the brand panel with three workflow steps', async () => {
    const { wrapper } = await mountSignup()
    expect(wrapper.find('[data-testid="signup-form"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="signup-brand-panel"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="signup-workflow-step"]')).toHaveLength(3)
  })

  it('blocks submit until the terms checkbox is accepted', async () => {
    const { wrapper, router } = await mountSignup()
    await fillValid(wrapper)
    // terms unchecked → submit blocked, error shown, no navigation
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/signup')
    expect(useAuthStore().accessToken).toBeNull()
    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
  })

  it('blocks submit when passwords do not match', async () => {
    const { wrapper, router } = await mountSignup()
    await wrapper.find('input[name="fullName"]').setValue('Ali')
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    await wrapper.find('input[name="password"]').setValue('11111111111')
    await wrapper.find('input[name="confirm"]').setValue('22222222222')
    await wrapper.find('[data-testid="signup-terms"]').setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('do not match')
    expect(router.currentRoute.value.path).toBe('/signup')
    expect(useAuthStore().accessToken).toBeNull()
  })

  it('signs up, stores display name locally, routes to dashboard', async () => {
    const { wrapper, router } = await mountSignup()
    await fillValid(wrapper)
    await wrapper.find('[data-testid="signup-terms"]').setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    const auth = useAuthStore()
    expect(auth.user?.email).toBe('new@indusia.example')
    expect(auth.displayName).toBe('Ali Sadikin')
    expect(localStorage.getItem('ive.display_name')).toBe('Ali Sadikin')
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('shows envelope error on duplicate email (409)', async () => {
    server.use(
      http.post('/api/auth/signup', () =>
        HttpResponse.json(
          { status: false, message: 'email already registered', data: null },
          { status: 409 },
        ),
      ),
    )
    const { wrapper } = await mountSignup()
    await fillValid(wrapper)
    await wrapper.find('[data-testid="signup-terms"]').setValue(true)
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('email already registered')
  })

  it('reveals the password when the show-password control is clicked', async () => {
    const { wrapper } = await mountSignup()
    await wrapper.find('[data-testid="signup-toggle-password"]').trigger('click')
    expect(wrapper.find('input[name="password"]').attributes('type')).toBe('text')
  })

  it('exposes the shared floating theme toggle', async () => {
    const { wrapper } = await mountSignup()
    expect(wrapper.find('[data-testid="auth-theme-toggle"]').exists()).toBe(true)
  })
})
