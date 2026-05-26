import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/signup',
    name: 'signup',
    component: () => import('@/views/auth/SignupView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/projects/:id/wizard',
    name: 'wizard',
    component: () => import('@/views/WizardView.vue'),
  },
  {
    path: '/projects/:id/labeling',
    name: 'labeling',
    component: () => import('@/views/LabelingView.vue'),
  },
  {
    path: '/projects/:id/gate1',
    name: 'gate1',
    component: () => import('@/views/Gate1View.vue'),
  },
  {
    path: '/projects/:id/training/:runId',
    name: 'training',
    component: () => import('@/views/TrainingView.vue'),
  },
  {
    path: '/projects/:id/eval/:runId',
    name: 'eval',
    component: () => import('@/views/EvalView.vue'),
  },
  {
    path: '/projects/:id/eval/:runId/gate2',
    name: 'gate2',
    component: () => import('@/views/Gate2View.vue'),
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
