import { describe, expect, it, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/projects', () => ({
  createProject: vi.fn(async (payload: { name: string; slug: string }) => ({
    id: 'new-id-123',
    name: payload.name,
    slug: payload.slug,
    status: 'drafting' as const,
    organization_id: 'org-1',
    created_at: '2026-05-27T00:00:00Z',
    updated_at: '2026-05-27T00:00:00Z',
  })),
}))

vi.mock('@/api/assets', () => ({
  uploadAsset: vi.fn(async (projectId: string, kind: string, file: File) => ({
    id: `asset-${kind}`,
    project_id: projectId,
    kind,
    path: `${projectId}/${kind}/${file.name}`,
    sha256: 'a'.repeat(64),
    mime: file.type || null,
    size_bytes: file.size,
    uploaded_at: '2026-05-27T00:00:00Z',
  })),
}))

vi.mock('@/api/bom', () => ({
  listBomItems: vi.fn(async (projectId: string) => [
    {
      id: 'b1',
      project_id: projectId,
      designator: 'R1',
      value: '10kΩ',
      package: '0805',
      qty: 2,
      position_hint: null,
      inspect_scope: 'pending' as const,
      mi_likely: false,
      component_type: 'smd_generic',
      defect_history_count: 0,
      extra: null,
    },
  ]),
}))

import { useWizardStore } from '@/stores/wizard'

describe('wizard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('starts on step "project"', () => {
    const wizard = useWizardStore()
    expect(wizard.currentStep).toBe('project')
    expect(wizard.canAdvance).toBe(false)
  })

  it('autofills slug from name on blur', () => {
    const wizard = useWizardStore()
    wizard.draftName = 'PCB Main Board v1'
    wizard.autofillSlug()
    expect(wizard.draftSlug).toBe('pcb-main-board-v1')
  })

  it('canAdvance true once name + slug filled', () => {
    const wizard = useWizardStore()
    wizard.draftName = 'PCB-A'
    wizard.draftSlug = 'pcb-a'
    expect(wizard.canAdvance).toBe(true)
  })

  it('next() on step 1 creates project and advances to step 2', async () => {
    const wizard = useWizardStore()
    wizard.draftName = 'PCB-A'
    wizard.draftSlug = 'pcb-a'
    await wizard.next()
    expect(wizard.project?.id).toBe('new-id-123')
    expect(wizard.currentStep).toBe('bom')
  })

  it('uploadAsset records the asset under its kind', async () => {
    const wizard = useWizardStore()
    wizard.draftName = 'PCB-A'
    wizard.draftSlug = 'pcb-a'
    await wizard.next() // creates project, advances to bom
    const file = new File(['x'], 'bom.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    await wizard.uploadAsset('bom', file)
    expect(wizard.assets.bom?.kind).toBe('bom')
    expect(wizard.canAdvance).toBe(true)
  })

  it('next() on bom step fetches bom items then advances', async () => {
    const wizard = useWizardStore()
    wizard.draftName = 'PCB-A'
    wizard.draftSlug = 'pcb-a'
    await wizard.next() // → bom
    const file = new File(['x'], 'bom.xlsx')
    await wizard.uploadAsset('bom', file)
    await wizard.next() // fetch bom items, → golden
    expect(wizard.bomItems.length).toBe(1)
    expect(wizard.currentStep).toBe('golden')
  })
})
