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
    id: `asset-${kind}-${file.name}`,
    project_id: projectId,
    kind,
    path: `${projectId}/${kind}/${file.name}`,
    sha256: 'a'.repeat(64),
    mime: file.type || null,
    size_bytes: file.size,
    uploaded_at: '2026-05-27T00:00:00Z',
  })),
  assetBinaryUrl: (projectId: string, assetId: string) =>
    `/api/projects/${projectId}/assets/${assetId}/binary`,
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

  // ───── G1: multi-sample golden set per side ─────

  async function newWizardWithProject() {
    const wizard = useWizardStore()
    wizard.draftName = 'PCB-A'
    wizard.draftSlug = 'pcb-a'
    await wizard.createProject()
    return wizard
  }

  it('uploading two golden_top boards appends to the array', async () => {
    const wizard = await newWizardWithProject()
    await wizard.uploadAsset('golden_top', new File(['1'], 'board-1.jpg', { type: 'image/jpeg' }))
    await wizard.uploadAsset('golden_top', new File(['2'], 'board-2.jpg', { type: 'image/jpeg' }))
    expect(wizard.goldenTop.length).toBe(2)
    expect(wizard.goldenBottom.length).toBe(0)
  })

  it('golden_top upload does NOT populate the single-slot assets map', async () => {
    const wizard = await newWizardWithProject()
    await wizard.uploadAsset('golden_top', new File(['1'], 'board-1.jpg', { type: 'image/jpeg' }))
    expect(wizard.assets.golden_top).toBeUndefined()
    // arrays are the source of truth
    expect(wizard.goldenTop.length).toBe(1)
  })

  it('canAdvance on golden step is true after one golden_top board', async () => {
    const wizard = await newWizardWithProject()
    // jump store to golden step
    wizard.stepIndex = 2
    expect(wizard.currentStep).toBe('golden')
    expect(wizard.canAdvance).toBe(false)
    await wizard.uploadAsset('golden_top', new File(['1'], 'board-1.jpg', { type: 'image/jpeg' }))
    expect(wizard.canAdvance).toBe(true)
  })

  it('removeGolden drops the matching board from the side array', async () => {
    const wizard = await newWizardWithProject()
    await wizard.uploadAsset('golden_top', new File(['1'], 'board-1.jpg', { type: 'image/jpeg' }))
    await wizard.uploadAsset('golden_top', new File(['2'], 'board-2.jpg', { type: 'image/jpeg' }))
    const removeId = wizard.goldenTop[0]!.id
    wizard.removeGolden('golden_top', removeId)
    expect(wizard.goldenTop.length).toBe(1)
    expect(wizard.goldenTop.some((a) => a.id === removeId)).toBe(false)
  })

  it('reset() clears both golden arrays', async () => {
    const wizard = await newWizardWithProject()
    await wizard.uploadAsset('golden_top', new File(['1'], 'board-1.jpg', { type: 'image/jpeg' }))
    await wizard.uploadAsset('golden_bottom', new File(['2'], 'board-2.jpg', { type: 'image/jpeg' }))
    wizard.reset()
    expect(wizard.goldenTop.length).toBe(0)
    expect(wizard.goldenBottom.length).toBe(0)
  })
})
