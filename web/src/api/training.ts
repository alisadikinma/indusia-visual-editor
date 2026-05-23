import { api, type ApiEnvelope } from "./client";
import type { DatasetStats } from "./dataset_stats";

export type Hyperparameters = {
  epochs: number;
  batch_size: number;
  augmentation_intensity: "low" | "medium" | "high";
  notes: string;
};

export type HyperparamsSuggestion = {
  project_id: string;
  side: "top" | "bottom";
  stats: DatasetStats;
  hyperparameters: Hyperparameters;
};

export type TrainRun = {
  id: string;
  project_id: string;
  adapt_run_id: string;
  service_job_id: string;
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  metrics_json: Record<string, unknown> | null;
  started_at: string;
  ended_at: string | null;
  error_text: string | null;
};

export async function suggestHyperparams(
  projectId: string,
  side: "top" | "bottom",
): Promise<HyperparamsSuggestion> {
  const r = await api.post<ApiEnvelope<HyperparamsSuggestion>>(
    `/api/projects/${projectId}/training/suggest-hyperparams`,
    null,
    { params: { side } },
  );
  return r.data.data;
}

export async function startTraining(projectId: string): Promise<TrainRun> {
  const r = await api.post<ApiEnvelope<TrainRun>>(
    `/api/projects/${projectId}/training/start`,
  );
  return r.data.data;
}

export function streamProgressUrl(runId: string): string {
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
  return `${base.replace(/\/+$/, "")}/api/training/${runId}/stream`;
}
