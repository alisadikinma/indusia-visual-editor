import { defineStore } from "pinia";

import {
  createProject as apiCreate,
  listProjects as apiList,
  type Project,
  type ProjectCreatePayload,
} from "../api/projects";

type State = {
  items: Project[];
  loading: boolean;
  error: string | null;
};

export const useProjectsStore = defineStore("projects", {
  state: (): State => ({
    items: [],
    loading: false,
    error: null,
  }),
  actions: {
    async fetch(): Promise<void> {
      this.loading = true;
      this.error = null;
      try {
        this.items = await apiList();
      } catch (e: unknown) {
        this.error = e instanceof Error ? e.message : "failed to fetch projects";
      } finally {
        this.loading = false;
      }
    },

    async create(payload: ProjectCreatePayload): Promise<Project> {
      this.error = null;
      const created = await apiCreate(payload);
      this.items = [created, ...this.items];
      return created;
    },
  },
});
