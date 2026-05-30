import { apiClient } from './client'

export type Side = 'top' | 'bottom'

export interface LsfResult {
  id: string
  type: string
  score?: number
  value: { rectanglelabels?: string[]; [k: string]: unknown }
  [k: string]: unknown
}

export interface LsfPrediction {
  model_version?: string
  score?: number
  result: LsfResult[]
}

export interface LsfTaskEnvelope {
  config: string
  task: {
    id: number
    data: { image: string }
    predictions: LsfPrediction[]
    annotations: unknown[]
  }
  side: Side
  designator_count: number
}

export interface LabelRow {
  id: string
  project_id: string
  side: Side
  version: number
  snapshot_at: string
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function getTask(projectId: string, side: Side): Promise<LsfTaskEnvelope> {
  const { data } = await apiClient.get<Envelope<LsfTaskEnvelope>>(
    `/projects/${projectId}/labels/task`,
    { params: { side } },
  )
  return data.data
}

export async function submitLabels(
  projectId: string,
  side: Side,
  lsJson: unknown,
): Promise<LabelRow> {
  const { data } = await apiClient.post<Envelope<LabelRow>>(
    `/projects/${projectId}/labels`,
    { ls_json: lsJson },
    { params: { side } },
  )
  return data.data
}

export async function listLabels(projectId: string): Promise<LabelRow[]> {
  const { data } = await apiClient.get<Envelope<LabelRow[]>>(
    `/projects/${projectId}/labels`,
  )
  return data.data
}

export async function runPrelabel(projectId: string, side: Side): Promise<unknown> {
  const { data } = await apiClient.post<Envelope<unknown>>(
    `/projects/${projectId}/llm/prelabel`,
    null,
    { params: { side } },
  )
  return data.data
}
