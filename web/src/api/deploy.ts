import { apiClient } from './client'

export interface Deployment {
  id: string
  project_id: string
  train_run_id: string
  model_version: string
  edges_notified: Array<{
    edge_id: string
    edge_name: string
    ok: boolean
    status_code: number | null
    error: string | null
  }>
  deployed_at: string
  sha256: string | null
  registry_tag: string | null
  push_command: string | null
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function promoteToProduction(projectId: string): Promise<Deployment> {
  const { data } = await apiClient.post<Envelope<Deployment>>(
    `/projects/${projectId}/deploy`,
    null,
  )
  return data.data
}

export async function listDeployments(projectId: string): Promise<Deployment[]> {
  const { data } = await apiClient.get<Envelope<Deployment[]>>(
    `/projects/${projectId}/deploy`,
  )
  return data.data
}
