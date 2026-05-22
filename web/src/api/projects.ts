import { api, type ApiEnvelope } from "./client";

export type ProjectStatus = "drafting" | "training" | "deployed" | "failed";

export type Project = {
  id: string;
  name: string;
  slug: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
};

export type ProjectCreatePayload = {
  name: string;
  slug: string;
};

export async function listProjects(): Promise<Project[]> {
  const response = await api.get<ApiEnvelope<Project[]>>("/api/projects");
  return response.data.data;
}

export async function createProject(payload: ProjectCreatePayload): Promise<Project> {
  const response = await api.post<ApiEnvelope<Project>>("/api/projects", payload);
  return response.data.data;
}
