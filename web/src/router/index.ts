import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";

import Dashboard from "@/views/Dashboard.vue";
import EvalView from "@/views/EvalView.vue";
import Gate1View from "@/views/Gate1View.vue";
import LabelingView from "@/views/LabelingView.vue";
import ProjectWizard from "@/views/ProjectWizard.vue";
import TrainingProgressView from "@/views/TrainingProgressView.vue";

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
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
