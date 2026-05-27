import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { i18n, setLocale } from './i18n'
import { useAuthStore } from './stores/auth'
import { useUiStore } from './stores/ui'
import './styles/main.css'

async function bootstrap() {
  // MSW intercepts dev-mode API calls by default. Set VITE_USE_MSW=false
  // (e.g. in web/.env.local) when smoke-testing against the real backend.
  const useMsw =
    import.meta.env.DEV && import.meta.env.VITE_USE_MSW !== 'false'
  if (useMsw) {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
  } else if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
    // Unregister any previously-installed MSW service worker so old caches
    // do not silently intercept real-backend calls.
    const regs = await navigator.serviceWorker.getRegistrations()
    await Promise.all(
      regs.map(async (r) => {
        if (r.active?.scriptURL?.includes('mockServiceWorker')) {
          await r.unregister()
        }
      }),
    )
  }

  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)
  app.use(router)
  app.use(i18n)

  const ui = useUiStore()
  setLocale(ui.locale)

  const auth = useAuthStore()
  if (auth.isAuthenticated) {
    await auth.loadCurrentUser()
  }

  app.mount('#app')
}

bootstrap()
