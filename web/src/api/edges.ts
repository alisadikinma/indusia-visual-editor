import { apiClient } from './client'

export interface VersionPolicy {
  mode: 'auto_pull_latest' | 'pinned'
  pinned_model?: string
  pinned_version?: string
}

export interface Edge {
  id: string
  name: string
  webhook_url: string
  version_policy: VersionPolicy
  registered_at: string
  last_seen_at: string | null
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function listEdges(): Promise<Edge[]> {
  const { data } = await apiClient.get<Envelope<Edge[]>>('/edges')
  return data.data
}

export async function registerEdge(payload: {
  name: string
  webhook_url: string
  version_policy?: VersionPolicy
}): Promise<Edge> {
  const { data } = await apiClient.post<Envelope<Edge>>('/edges', payload)
  return data.data
}

export async function updateEdgePolicy(
  edgeId: string,
  versionPolicy: VersionPolicy,
): Promise<Edge> {
  const { data } = await apiClient.put<Envelope<Edge>>(`/edges/${edgeId}`, {
    version_policy: versionPolicy,
  })
  return data.data
}

export async function pinEdge(
  edgeId: string,
  modelName: string | null,
  version: string | null,
): Promise<Edge> {
  const { data } = await apiClient.put<Envelope<Edge>>(`/edges/${edgeId}/pin`, {
    model_name: modelName,
    version,
  })
  return data.data
}
