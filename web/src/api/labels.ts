import { api, type ApiEnvelope } from "./client";

export type LsfTask = {
  id: number;
  data: { image: string };
  predictions: unknown[];
  annotations: unknown[];
};

export type LabelingTask = {
  config: string;
  task: LsfTask;
  side: "top" | "bottom";
  designator_count: number;
};

export type LabelSnapshot = {
  id: string;
  project_id: string;
  side: "top" | "bottom";
  version: number;
  snapshot_at: string;
};

/**
 * Backend emits relative URLs (`/api/projects/{pid}/assets/{aid}/binary`)
 * because the Vite dev server runs on a different origin than the API.
 * LSF fetches images itself; it needs the absolute URL.
 */
export function absoluteImageUrl(relativePath: string): string {
  if (/^https?:\/\//i.test(relativePath)) return relativePath;
  const base = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
  return `${base.replace(/\/+$/, "")}${relativePath}`;
}

export async function getTask(
  projectId: string,
  side: "top" | "bottom",
): Promise<LabelingTask> {
  const r = await api.get<ApiEnvelope<LabelingTask>>(
    `/api/projects/${projectId}/labels/task`,
    { params: { side } },
  );
  // Rewrite the relative image URL so LSF can fetch it directly.
  const data = r.data.data;
  data.task.data.image = absoluteImageUrl(data.task.data.image);
  return data;
}

export async function submitLabels(
  projectId: string,
  side: "top" | "bottom",
  lsJson: { result: unknown[] },
): Promise<LabelSnapshot> {
  const r = await api.post<ApiEnvelope<LabelSnapshot>>(
    `/api/projects/${projectId}/labels`,
    { ls_json: lsJson },
    { params: { side } },
  );
  return r.data.data;
}
