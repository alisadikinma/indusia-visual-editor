import { apiClient } from './client'

export type InspectScope = 'pending' | 'inspected' | 'skipped'

export interface BomItem {
  id: string
  project_id: string
  designator: string
  value: string | null
  package: string | null
  qty: number | null
  position_hint: string | null
  inspect_scope: InspectScope
  mi_likely: boolean | null
  component_type: string | null
  defect_history_count: number
  extra: Record<string, unknown> | null
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function listBomItems(projectId: string): Promise<BomItem[]> {
  const { data } = await apiClient.get<Envelope<BomItem[]>>(
    `/projects/${projectId}/bom_items`,
  )
  return data.data
}
