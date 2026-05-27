import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { i18n, setLocale } from './i18n'
import { useAuthStore } from './stores/auth'
import { useUiStore } from './stores/ui'
import './styles/main.css'

async function bootstrap() {
  if (import.meta.env.DEV) {
    const { worker } = await import('./mocks/browser')
    await worker.start({ onUnhandledRequest: 'bypass' })
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
