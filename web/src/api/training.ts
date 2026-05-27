import { apiClient } from './client'
import type { Side } from './labels'

export type TrainStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface TrainRun {
  id: string
  project_id: string
  adapt_run_id: string
  service_job_id: string
  status: TrainStatus
  metrics_json: Record<string, unknown> | null
  started_at: string
  ended_at: string | null
  error_text: string | null
}

export interface DatasetStats {
  total_regions: number
  per_designator: Array<{
    designator: string
    count: number
    bucket: 'sufficient' | 'moderate' | 'at_risk'
  }>
  coverage_ratio: number
  side_breakdown: { top: number; bottom: number }
}

export interface HyperparamsSuggestion {
  project_id: string
  side: Side
  stats: DatasetStats
  hyperparameters: {
    epochs: number
    batch_size: number
    learning_rate: number
    augmentation_intensity: 'low' | 'medium' | 'high'
    early_stopping_patience: number
    grounding_source: string
  }
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function getDatasetStats(projectId: string): Promise<DatasetStats> {
  const { data } = await apiClient.get<Envelope<DatasetStats>>(
    `/projects/${projectId}/dataset/stats`,
  )
  return data.data
}

export async function suggestHyperparams(
  projectId: string,
  side: Side,
): Promise<HyperparamsSuggestion> {
  const { data } = await apiClient.post<Envelope<HyperparamsSuggestion>>(
    `/projects/${projectId}/training/suggest-hyperparams`,
    null,
    { params: { side } },
  )
  return data.data
}

export async function startTraining(projectId: string): Promise<TrainRun> {
  const { data } = await apiClient.post<Envelope<TrainRun>>(
    `/projects/${projectId}/training/start`,
    null,
  )
  return data.data
}

export async function listTrainRuns(projectId: string): Promise<TrainRun[]> {
  const { data } = await apiClient.get<Envelope<TrainRun[]>>(`/projects/${projectId}/training`)
  return data.data
}

export function streamTrainingUrl(runId: string): string {
  return `/api/training/${runId}/stream`
}
