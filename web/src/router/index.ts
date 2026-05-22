import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import Dashboard from "@/views/Dashboard.vue";
import ProjectWizard from "@/views/ProjectWizard.vue";

export const routes: RouteRecordRaw[] = [
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
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
