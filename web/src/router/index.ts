import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true, titleKey: 'auth.loginTitle' },
  },
  {
    path: '/signup',
    name: 'signup',
    component: () => import('@/views/auth/SignupView.vue'),
    meta: { public: true, titleKey: 'auth.signupTitle' },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { titleKey: 'nav.dashboard' },
  },
  {
    path: '/projects/new',
    redirect: '/projects/new/wizard',
  },
  {
    path: '/projects/:id/wizard',
    name: 'wizard',
    component: () => import('@/views/WizardView.vue'),
    meta: { titleKey: 'nav.wizard' },
  },
  {
    path: '/projects/:id/labeling',
    name: 'labeling',
    component: () => import('@/views/LabelingView.vue'),
    meta: { titleKey: 'nav.labeling' },
  },
  {
    path: '/projects/:id/gate1',
    name: 'gate1',
    component: () => import('@/views/Gate1View.vue'),
    meta: { titleKey: 'nav.gate1' },
  },
  {
    path: '/projects/:id/training/:runId',
    name: 'training',
    component: () => import('@/views/TrainingView.vue'),
    meta: { titleKey: 'nav.training' },
  },
  {
    path: '/projects/:id/setup-eval/:runId',
    name: 'setup-eval',
    component: () => import('@/views/SetupEvalView.vue'),
    meta: { titleKey: 'nav.setupEval' },
  },
  {
    path: '/projects/:id/eval/:runId',
    name: 'eval',
    component: () => import('@/views/EvalView.vue'),
    meta: { titleKey: 'nav.eval' },
  },
  {
    path: '/projects/:id/eval/:runId/gate2',
    name: 'gate2',
    component: () => import('@/views/Gate2View.vue'),
    meta: { titleKey: 'nav.gate2' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const isPublic = to.meta.public === true
  if (!isPublic && !auth.isAuthenticated) {
    return { name: 'login', query: { next: to.fullPath } }
  }
  if (isPublic && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
  return true
})
