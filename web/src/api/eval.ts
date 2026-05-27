import { apiClient } from './client'

export interface PerComponentMetric {
  designator: string
  f1: number
  precision: number
  recall: number
  support: number
  pass: boolean
}

export interface EvalMetrics {
  map: number
  f1_macro: number
  precision_macro: number
  recall_macro: number
  per_component: PerComponentMetric[]
  false_positives: number
  false_negatives: number
}

export interface EvalPrediction {
  id: string
  designator: string
  status: 'tp' | 'fp' | 'fn' | 'tn'
  confidence: number
  thumbnail_url: string | null
}

export interface EvalResponse {
  run_id: string
  metrics: EvalMetrics
  predictions: EvalPrediction[]
  prev_metrics: EvalMetrics | null
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function getEval(runId: string): Promise<EvalResponse> {
  const { data } = await apiClient.get<Envelope<EvalResponse>>(`/training/${runId}/eval`)
  return data.data
}

// Thresholds locked in spec §14
export const EVAL_THRESHOLDS = {
  map_min: 0.8,
  f1_macro_min: 0.8,
  per_component_f1_min: 0.7,
} as const

export type EvalVerdict = 'failing' | 'corrected' | 'passed'

export function classifyEval(metrics: EvalMetrics, hasCorrections: boolean): EvalVerdict {
  const mapOk = metrics.map >= EVAL_THRESHOLDS.map_min
  const macroOk = metrics.f1_macro >= EVAL_THRESHOLDS.f1_macro_min
  const allPerCompOk = metrics.per_component.every(
    (p) => p.f1 >= EVAL_THRESHOLDS.per_component_f1_min,
  )
  if (mapOk && macroOk && allPerCompOk) return 'passed'
  if (hasCorrections) return 'corrected'
  return 'failing'
}
