import { api, type ApiEnvelope } from "./client";

export type DesignatorStat = {
  designator: string;
  inspect_scope: "inspected" | "skipped";
  scope_mode: "per_component" | "whole_side";
  defect_criteria: string[];
  mi_likely: boolean | null;
};

export type DatasetStats = {
  project_id: string;
  side: "top" | "bottom";
  label_version: number;
  total: number;
  inspected: number;
  skipped: number;
  per_criterion: Record<string, number>;
  mi_count: number;
  smt_count: number;
  designators: DesignatorStat[];
};

export async function getDatasetStats(
  projectId: string,
  side: "top" | "bottom",
): Promise<DatasetStats> {
  const r = await api.get<ApiEnvelope<DatasetStats>>(
    `/api/projects/${projectId}/dataset/stats`,
    { params: { side } },
  );
  return r.data.data;
}
