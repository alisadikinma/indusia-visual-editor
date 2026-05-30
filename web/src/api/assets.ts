import { apiClient } from './client'

export type AssetKind = 'bom' | 'golden_top' | 'golden_bottom' | 'drawing'

export type QcVerdict = 'ok' | 'warn' | 'fail'

export interface GoldenQc {
  verdict: QcVerdict
  reasons: string[]
  sharpness: number
  mean_luminance: number
  clipped_dark: number
  clipped_bright: number
}

export interface Asset {
  id: string
  project_id: string
  kind: AssetKind
  path: string
  sha256: string
  mime: string | null
  size_bytes: number | null
  uploaded_at: string
  // Present on the upload response for golden_top/golden_bottom images (T6/G4).
  qc?: GoldenQc
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function uploadAsset(
  projectId: string,
  kind: AssetKind,
  file: File,
): Promise<Asset> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<Envelope<Asset>>(
    `/projects/${projectId}/assets`,
    form,
    {
      params: { kind },
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  )
  return data.data
}

export async function listAssets(projectId: string): Promise<Asset[]> {
  const { data } = await apiClient.get<Envelope<Asset[]>>(`/projects/${projectId}/assets`)
  return data.data
}

export function assetBinaryUrl(projectId: string, assetId: string): string {
  return `/api/projects/${projectId}/assets/${assetId}/binary`
}

export async function getAssetQc(projectId: string, assetId: string): Promise<GoldenQc> {
  const { data } = await apiClient.get<Envelope<GoldenQc>>(
    `/projects/${projectId}/assets/${assetId}/qc`,
  )
  return data.data
}

export interface RegistrationPreflight {
  verdict: QcVerdict
  reasons: string[]
  per_image: { keypoints: number; ok: boolean }[]
  pairwise_residual_px: number | null
  sample_count: number
}

export async function getRegistrationPreflight(
  projectId: string,
  side: 'top' | 'bottom',
): Promise<RegistrationPreflight> {
  const { data } = await apiClient.get<Envelope<RegistrationPreflight>>(
    `/projects/${projectId}/registration-preflight`,
    { params: { side } },
  )
  return data.data
}
