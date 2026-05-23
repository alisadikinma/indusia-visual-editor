import { api, type ApiEnvelope } from "./client";

export type EvalPrediction = {
  designator: string;
  bbox: [number, number, number, number];
  verdict: "pass" | "fail" | "uncertain";
  is_false_positive: boolean;
  is_false_negative: boolean;
  score: number;
};

export type EvalMetrics = {
  mAP?: number;
  per_component_f1?: Record<string, number>;
  [key: string]: unknown;
};

export type EvalResult = {
  run_id: string;
  metrics: EvalMetrics;
  predictions: EvalPrediction[];
  prev_metrics: EvalMetrics | null;
};

export async function getEval(runId: string): Promise<EvalResult> {
  const r = await api.get<ApiEnvelope<EvalResult>>(
    `/api/training/${runId}/eval`,
  );
  return r.data.data;
}
