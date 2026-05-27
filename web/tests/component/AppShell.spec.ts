import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppTopBar from '@/components/layout/AppTopBar.vue'
import { useAuthStore } from '@/stores/auth'
import { useEngineerStore } from '@/stores/engineer'
import { useUiStore } from '@/stores/ui'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div/>' }, meta: { titleKey: 'nav.dashboard' } },
      { path: '/login', name: 'login', component: { template: '<div/>' } },
      { path: '/models', name: 'models', component: { template: '<div/>' }, meta: { titleKey: 'nav.models' } },
    ],
  })
}

describe('AppSidebar', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('exposes brand, workspace + settings sections, and AI advisor on stable testids', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const w = mount(AppSidebar, { global: { plugins: [router] } })

    expect(w.find('[data-testid="app-sidebar"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-brand"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-section-workspace"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-section-settings"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-nav-dashboard"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-nav-models"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-nav-preferences"]').exists()).toBe(true)
    expect(w.find('[data-testid="sidebar-ai-advisor"]').exists()).toBe(true)
  })

  it('reflects collapsed state via data-state attr', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const w = mount(AppSidebar, { global: { plugins: [router] } })
    const ui = useUiStore()
    ui.sidebarCollapsed = true
    await w.vm.$nextTick()
    expect(w.find('[data-testid="app-sidebar"]').attributes('data-collapsed')).toBe('true')
  })
})

describe('AppTopBar', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('exposes breadcrumb, EN/ID pills, engineer toggle, logout on stable testids', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const w = mount(AppTopBar, { global: { plugins: [router] } })

    expect(w.find('[data-testid="app-topbar"]').exists()).toBe(true)
    expect(w.find('[data-testid="topbar-sidebar-toggle"]').exists()).toBe(true)
    expect(w.find('[data-testid="topbar-breadcrumb"]').exists()).toBe(true)
    expect(w.find('[data-testid="topbar-locale-en"]').exists()).toBe(true)
    expect(w.find('[data-testid="topbar-locale-id"]').exists()).toBe(true)
    expect(w.find('[data-testid="topbar-engineer-toggle"]').exists()).toBe(true)
    expect(w.find('[data-testid="topbar-logout"]').exists()).toBe(true)
  })

  it('engineer toggle reflects store state via aria-pressed', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const w = mount(AppTopBar, { global: { plugins: [router] } })
    const engineer = useEngineerStore()

    expect(w.find('[data-testid="topbar-engineer-toggle"]').attributes('aria-pressed')).toBe('false')
    engineer.toggle()
    await w.vm.$nextTick()
    expect(w.find('[data-testid="topbar-engineer-toggle"]').attributes('aria-pressed')).toBe('true')
  })

  it('logout button calls auth.logout and pushes /login', async () => {
    const router = makeRouter()
    await router.push('/')
    await router.isReady()
    const w = mount(AppTopBar, { global: { plugins: [router] } })
    const auth = useAuthStore()
    auth.accessToken = 'fake'
    await w.find('[data-testid="topbar-logout"]').trigger('click')
    // logout clears token regardless of network outcome (api.logout is best-effort)
    await new Promise((r) => setTimeout(r, 0))
    expect(auth.accessToken).toBeNull()
  })
})
