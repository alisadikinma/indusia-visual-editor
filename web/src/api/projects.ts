import { apiClient } from './client'

export type ProjectStatus = 'drafting' | 'training' | 'deployed' | 'failed'

export interface Project {
  id: string
  name: string
  slug: string
  status: ProjectStatus
  organization_id: string
  created_at: string
  updated_at: string
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function listProjects(): Promise<Project[]> {
  const { data } = await apiClient.get<Envelope<Project[]>>('/projects')
  return data.data
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await apiClient.get<Envelope<Project>>(`/projects/${id}`)
  return data.data
}

export async function createProject(payload: {
  name: string
  slug: string
}): Promise<Project> {
  const { data } = await apiClient.post<Envelope<Project>>('/projects', payload)
  return data.data
}

export async function updateProject(
  id: string,
  payload: Partial<{ name: string; slug: string; status: ProjectStatus }>,
): Promise<Project> {
  const { data } = await apiClient.put<Envelope<Project>>(`/projects/${id}`, payload)
  return data.data
}
