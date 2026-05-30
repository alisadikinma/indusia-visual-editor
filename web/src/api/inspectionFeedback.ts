import { apiClient } from './client'

export type ModelVerdict = 'pass' | 'fail' | 'uncertain'
export type OperatorMark = 'confirmed' | 'escape' | 'overkill'
export type FeedbackStatus = 'new' | 'curated' | 'promoted' | 'dismissed'

export interface FeedbackItem {
  id: string
  project_id: string
  edge_id: string | null
  train_run_id: string | null
  designator: string | null
  model_verdict: ModelVerdict
  operator_mark: OperatorMark | null
  defect_criterion: string | null
  roi_path: string | null
  roi_sha256: string | null
  status: FeedbackStatus
  inspection_ts: string | null
  created_at: string
}

export interface DefectExample {
  id: string
  project_id: string
  source_feedback_id: string | null
  designator: string | null
  defect_criterion: string
  roi_path: string
  roi_sha256: string
  created_at: string
}

export interface IngestPayload {
  edge_id?: string | null
  train_run_id?: string | null
  designator?: string | null
  model_verdict: ModelVerdict
  operator_mark?: OperatorMark | null
  defect_criterion?: string | null
  inspection_ts?: string | null
}

export interface CuratePayload {
  operator_mark?: OperatorMark | null
  status?: FeedbackStatus
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function listFeedback(status?: FeedbackStatus): Promise<FeedbackItem[]> {
  const { data } = await apiClient.get<Envelope<FeedbackItem[]>>('/inspection-feedback', {
    params: status ? { status } : undefined,
  })
  return data.data
}

export async function ingestFeedback(
  projectId: string,
  payload: IngestPayload,
  roiFile?: File,
): Promise<FeedbackItem> {
  const form = new FormData()
  for (const [key, value] of Object.entries(payload)) {
    if (value !== undefined && value !== null) {
      form.append(key, String(value))
    }
  }
  if (roiFile) {
    form.append('file', roiFile)
  }
  const { data } = await apiClient.post<Envelope<FeedbackItem>>(
    `/projects/${projectId}/inspection-feedback`,
    form,
  )
  return data.data
}

export async function curateFeedback(
  feedbackId: string,
  body: CuratePayload,
): Promise<FeedbackItem> {
  const { data } = await apiClient.put<Envelope<FeedbackItem>>(
    `/inspection-feedback/${feedbackId}`,
    body,
  )
  return data.data
}

export async function promoteFeedback(feedbackId: string): Promise<DefectExample> {
  const { data } = await apiClient.post<Envelope<DefectExample>>(
    `/inspection-feedback/${feedbackId}/promote`,
  )
  return data.data
}
