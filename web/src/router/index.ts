import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import Dashboard from "@/views/Dashboard.vue";
import EvalView from "@/views/EvalView.vue";
import Gate1View from "@/views/Gate1View.vue";
import Gate2View from "@/views/Gate2View.vue";
import LabelingView from "@/views/LabelingView.vue";
import LoginView from "@/views/LoginView.vue";
import ProjectWizard from "@/views/ProjectWizard.vue";
import SignupView from "@/views/SignupView.vue";
import TrainingProgressView from "@/views/TrainingProgressView.vue";

import { useAuthStore } from "@/stores/auth";

export const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: LoginView,
    meta: { public: true },
  },
  {
    path: "/signup",
    name: "signup",
    component: SignupView,
    meta: { public: true },
  },
  {
    path: "/",
    name: "dashboard",
    component: Dashboard,
  },
  {
    path: "/projects/:id/wizard",
    name: "project-wizard",
    component: ProjectWizard,
  },
  {
    path: "/projects/:id/labeling",
    name: "project-labeling",
    component: LabelingView,
  },
  {
    path: "/projects/:id/gate1",
    name: "gate1",
    component: Gate1View,
  },
  {
    path: "/projects/:id/training/:runId",
    name: "training-progress",
    component: TrainingProgressView,
  },
  {
    path: "/projects/:id/eval/:runId",
    name: "eval",
    component: EvalView,
  },
  {
    path: "/projects/:id/eval/:runId/gate2",
    name: "gate2",
    component: Gate2View,
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  // Allow login + signup unconditionally; bounce back to / when already authed.
  if (to.meta.public) {
    if (auth.isAuthenticated && (to.name === "login" || to.name === "signup")) {
      return { path: "/" };
    }
    return true;
  }
  if (!auth.isAuthenticated) {
    return { path: "/login", query: { next: to.fullPath } };
  }
  return true;
});
