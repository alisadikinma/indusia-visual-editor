import { api, type ApiEnvelope } from "./client";

export type PreLabeledRegion = {
  designator: string;
  bbox: [number, number, number, number];
  confidence: number;
  side: "top" | "bottom";
};

export type PreLabelRun = {
  id: string;
  project_id: string;
  side: "top" | "bottom";
  regions: PreLabeledRegion[];
  created_at: string;
};

export async function runPreLabel(
  projectId: string,
  side: "top" | "bottom",
): Promise<PreLabelRun> {
  const r = await api.post<ApiEnvelope<PreLabelRun>>(
    `/api/projects/${projectId}/llm/prelabel`,
    null,
    { params: { side } },
  );
  return r.data.data;
}

export async function getPreLabel(
  projectId: string,
  side: "top" | "bottom",
): Promise<PreLabelRun | null> {
  try {
    const r = await api.get<ApiEnvelope<PreLabelRun>>(
      `/api/projects/${projectId}/llm/prelabel`,
      { params: { side } },
    );
    return r.data.data;
  } catch (e: unknown) {
    // 404 → no pre-label yet; surface as null
    const status = (e as { response?: { status?: number } }).response?.status;
    if (status === 404) return null;
    throw e;
  }
}
