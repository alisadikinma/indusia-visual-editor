import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { http, HttpResponse } from 'msw'
import LoginView from '@/views/auth/LoginView.vue'
import { server } from '@/mocks/server'
import { useAuthStore } from '@/stores/auth'

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

async function mountLogin() {
  const router = makeRouter()
  await router.push('/login')
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
    const router = makeRouter()
    await router.push('/login?next=/projects/abc/wizard')
    await router.isReady()
    const wrapper = mount(LoginView, {
      global: { plugins: [router] },
      attachTo: document.body,
    })
    await wrapper.find('input[type="email"]').setValue('demo@indusia.example')
    await wrapper.find('input[type="password"]').setValue('any-password')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/projects/abc/wizard')
  })
})
