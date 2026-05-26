import { defineStore } from "pinia";

import {
  getTask as apiGetTask,
  submitLabels as apiSubmitLabels,
  type LabelingTask,
  type LabelSnapshot,
} from "../api/labels";
import { runPreLabel as apiRunPreLabel } from "../api/prelabel";

type Side = "top" | "bottom";

type State = {
  side: Side;
  task: LabelingTask | null;
  loading: boolean;
  saving: boolean;
  refreshing: boolean;
  error: string | null;
  latest: LabelSnapshot | null;
};

function extractErrorMessage(e: unknown): string {
  const respMsg = (e as {
    response?: { data?: { message?: string } };
  }).response?.data?.message;
  if (typeof respMsg === "string" && respMsg.length > 0) return respMsg;
  if (e instanceof Error) return e.message;
  return "Terjadi kesalahan";
}

export const useLabelsStore = defineStore("labels", {
  state: (): State => ({
    side: "top",
    task: null,
    loading: false,
    saving: false,
    refreshing: false,
    error: null,
    latest: null,
  }),
  actions: {
    async fetchTask(projectId: string, side: Side) {
      this.loading = true;
      this.error = null;
      this.side = side;
      try {
        this.task = await apiGetTask(projectId, side);
      } catch (e) {
        this.task = null;
        this.error = extractErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },
    async refreshPredictions(projectId: string) {
      this.refreshing = true;
      this.error = null;
      try {
        await apiRunPreLabel(projectId, this.side);
        this.task = await apiGetTask(projectId, this.side);
      } catch (e) {
        this.error = extractErrorMessage(e);
      } finally {
        this.refreshing = false;
      }
    },
    async submit(projectId: string, lsJson: { result: unknown[] }) {
      this.saving = true;
      this.error = null;
      try {
        this.latest = await apiSubmitLabels(projectId, this.side, lsJson);
      } catch (e) {
        this.error = extractErrorMessage(e);
      } finally {
        this.saving = false;
      }
    },
    reset() {
      this.task = null;
      this.error = null;
      this.latest = null;
      this.loading = false;
      this.saving = false;
      this.refreshing = false;
      this.side = "top";
    },
  },
});
