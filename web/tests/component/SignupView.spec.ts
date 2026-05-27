import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import SignupView from '@/views/auth/SignupView.vue'
import { server } from '@/mocks/server'
import { useAuthStore } from '@/stores/auth'

async function mountSignup() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div>dash</div>' } },
      { path: '/signup', name: 'signup', component: SignupView },
      { path: '/login', name: 'login', component: { template: '<div>login</div>' } },
    ],
  })
  await router.push('/signup')
  await router.isReady()
  const wrapper = mount(SignupView, { global: { plugins: [router] }, attachTo: document.body })
  return { wrapper, router }
}

describe('SignupView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('renders heading + 4 form fields', async () => {
    const { wrapper } = await mountSignup()
    expect(wrapper.text()).toContain('Create account')
    expect(wrapper.findAll('input').length).toBeGreaterThanOrEqual(4)
  })

  it('blocks submit when passwords do not match', async () => {
    const { wrapper, router } = await mountSignup()
    await wrapper.find('input[type="email"]').setValue('a@b.com')
    const pwInputs = wrapper.findAll('input[type="password"]')
    await pwInputs[0].setValue('11111111')
    await pwInputs[1].setValue('22222222')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('do not match')
    expect(router.currentRoute.value.path).toBe('/signup')
    expect(useAuthStore().accessToken).toBeNull()
  })

  it('signs up and routes to dashboard on success', async () => {
    const { wrapper, router } = await mountSignup()
    await wrapper.find('input[type="email"]').setValue('new@indusia.example')
    const pwInputs = wrapper.findAll('input[type="password"]')
    await pwInputs[0].setValue('strongpass')
    await pwInputs[1].setValue('strongpass')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(useAuthStore().user?.email).toBe('new@indusia.example')
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
    await wrapper.find('input[type="email"]').setValue('dup@indusia.example')
    const pwInputs = wrapper.findAll('input[type="password"]')
    await pwInputs[0].setValue('strongpass')
    await pwInputs[1].setValue('strongpass')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').text()).toContain('email already registered')
  })
})
