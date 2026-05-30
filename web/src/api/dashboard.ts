import { apiClient } from './client'
import type { ProjectStatus } from './projects'

// Cross-project rollup from GET /api/dashboard/summary (Bundle 2.0). Every
// field traces to a real row — there are deliberately NO trend deltas and no
// 7-day inspection series here, because no telemetry table backs them. The
// DashboardView hides those affordances rather than render invented numbers.
export interface DashboardStats {
  active_projects: number
  drafting: number
  training: number
  deployed: number
  failed: number
  models_deployed: number
  edges_online: number
  edges_total: number
  avg_map: number | null
}

export interface DashboardProject {
  id: string
  name: string
  slug: string
  status: ProjectStatus
  updated_at: string | null
  bom_count: number
  latest_map: number | null
}

export interface DashboardSummary {
  stats: DashboardStats
  projects: DashboardProject[]
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<Envelope<DashboardSummary>>('/dashboard/summary')
  return data.data
}
