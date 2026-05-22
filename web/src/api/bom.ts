import { api, type ApiEnvelope } from "./client";

export type InspectScope = "pending" | "inspected" | "skipped";

export type BomItem = {
  id: string;
  project_id: string;
  designator: string;
  value: string | null;
  package: string | null;
  qty: number | null;
  position_hint: string | null;
  inspect_scope: InspectScope;
  mi_likely: boolean | null;
  component_type: string | null;
  defect_history_count: number;
  extra: Record<string, string> | null;
};

export async function listBomItems(projectId: string): Promise<BomItem[]> {
  const r = await api.get<ApiEnvelope<BomItem[]>>(
    `/api/projects/${projectId}/bom_items`,
  );
  return r.data.data;
}

export async function uploadBom(projectId: string, file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  await api.post(`/api/projects/${projectId}/assets?kind=bom`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
