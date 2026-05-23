import { api, type ApiEnvelope } from "./client";

export type Deployment = {
  id: string;
  project_id: string;
  train_run_id: string;
  model_version: string;
  status: "pending" | "succeeded" | "failed";
  edges_notified: Record<string, unknown> | null;
  deployed_at: string;
  error_text: string | null;
};

export async function promoteToProduction(
  projectId: string,
): Promise<Deployment> {
  const r = await api.post<ApiEnvelope<Deployment>>(
    `/api/projects/${projectId}/deploy`,
  );
  return r.data.data;
}

export async function getDeployHistory(
  projectId: string,
): Promise<Deployment[]> {
  const r = await api.get<ApiEnvelope<Deployment[]>>(
    `/api/projects/${projectId}/deploy`,
  );
  return r.data.data;
}
