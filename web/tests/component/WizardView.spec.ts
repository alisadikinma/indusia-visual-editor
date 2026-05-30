import { describe, expect, it, beforeEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import WizardView from '@/views/WizardView.vue'
import { useWizardStore } from '@/stores/wizard'
import type { Asset, AssetKind } from '@/api/assets'
import type { BomItem } from '@/api/bom'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'dashboard', component: { template: '<div>dash</div>' } },
      { path: '/projects/:id/wizard', name: 'wizard', component: WizardView },
      { path: '/projects/:id/labeling', name: 'labeling', component: { template: '<div>lab</div>' } },
    ],
  })
}

async function mountWizard(id = 'new') {
  const router = makeRouter()
  await router.push({ name: 'wizard', params: { id } })
  await router.isReady()
  const wrapper = mount(WizardView, {
    global: { plugins: [router] },
    attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, router }
}

function fakeAsset(kind: AssetKind, size: number): Asset {
  return {
    id: `a-${kind}`,
    project_id: 'p1',
    kind,
    path: `storage/p1/${kind}/abc.${kind === 'bom' ? 'xlsx' : 'png'}`,
    sha256: 'abc',
    mime: kind === 'bom' ? 'application/vnd.ms-excel' : 'image/png',
    size_bytes: size,
    uploaded_at: '2026-05-30T00:00:00Z',
  }
}

const SAMPLE_BOM: BomItem[] = [
  {
    id: 'b1',
    project_id: 'p1',
    designator: 'C63',
    value: 'Cap,Elec,330uF,63v',
    package: 'Radial',
    qty: 4,
    position_hint: null,
    inspect_scope: 'pending',
    mi_likely: true,
    component_type: 'electrolytic_cap',
    defect_history_count: 0,
    extra: null,
  },
  {
    id: 'b2',
    project_id: 'p1',
    designator: 'C76',
    value: 'Cap,Cerm,0.1uF',
    package: '0805',
    qty: 1,
    position_hint: null,
    inspect_scope: 'pending',
    mi_likely: false,
    component_type: 'smd_generic',
    defect_history_count: 0,
    extra: null,
  },
]

async function jumpTo(wrapper: VueWrapper, stepIndex: number) {
  const store = useWizardStore()
  store.stepIndex = stepIndex
  await nextTick()
  await flushPromises()
}

describe('WizardView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders the 5-step stepper with labels', async () => {
    const { wrapper } = await mountWizard()
    for (const n of [1, 2, 3, 4, 5]) {
      expect(wrapper.find(`[data-testid="wizard-step-${n}"]`).exists()).toBe(true)
    }
    const text = wrapper.get('[data-testid="wizard-stepper"]').text()
    expect(text).toContain('Project info')
    expect(text).toContain('BOM upload')
    expect(text).toContain('Review')
  })

  it('step 1 shows project detail inputs and the setup checklist', async () => {
    const { wrapper } = await mountWizard()
    expect(wrapper.find('[data-testid="wizard-name-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="wizard-slug-input"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="wizard-checklist"]').exists()).toBe(true)
  })

  it('autofills the slug from the project name on blur', async () => {
    const { wrapper } = await mountWizard()
    const store = useWizardStore()
    const name = wrapper.get('[data-testid="wizard-name-input"]')
    await name.setValue('Mainboard XR-200')
    await name.trigger('blur')
    expect(store.draftSlug).toBe('mainboard-xr-200')
  })

  it('continue on step 1 creates the project and advances to BOM', async () => {
    const { wrapper, router } = await mountWizard()
    const store = useWizardStore()
    store.draftName = 'Wizard Test Board'
    store.draftSlug = 'wizard-test-board'
    await nextTick()
    await wrapper.get('[data-testid="wizard-continue"]').trigger('click')
    await flushPromises()
    expect(store.project).not.toBeNull()
    expect(store.currentStep).toBe('bom')
    expect(router.currentRoute.value.params.id).toBe(store.project?.id)
  })

  it('step 2 shows the BOM dropzone, parse summary and preview table', async () => {
    const { wrapper } = await mountWizard()
    const store = useWizardStore()
    store.project = { id: 'p1', name: 'X', slug: 'x', status: 'drafting', organization_id: 'o', created_at: '', updated_at: '' }
    store.assets = { bom: fakeAsset('bom', 188_416) }
    store.bomItems = SAMPLE_BOM
    await jumpTo(wrapper, 1)
    expect(wrapper.find('[data-testid="wizard-bom-dropzone"]').exists()).toBe(true)
    const summary = wrapper.get('[data-testid="wizard-parse-summary"]').text()
    expect(summary).toContain('2') // 2 BOM items detected
    expect(summary).toContain('1') // 1 MI-likely
    const table = wrapper.get('[data-testid="wizard-bom-table"]').text()
    expect(table).toContain('C63')
    expect(table).toContain('electrolytic_cap')
  })

  it('step 3 shows two golden dropzones and the photo tips sidebar', async () => {
    const { wrapper } = await mountWizard()
    await jumpTo(wrapper, 2)
    expect(wrapper.find('[data-testid="wizard-golden-top"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="wizard-golden-bottom"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="wizard-photo-tips"]').exists()).toBe(true)
  })

  it('step 4 shows the drawing dropzone and example card', async () => {
    const { wrapper } = await mountWizard()
    await jumpTo(wrapper, 3)
    expect(wrapper.find('[data-testid="wizard-drawing-dropzone"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="wizard-drawing-example"]').exists()).toBe(true)
  })

  it('step 5 shows review rows, what-happens-next and a Create button', async () => {
    const { wrapper } = await mountWizard()
    const store = useWizardStore()
    store.project = { id: 'p1', name: 'Mainboard XR-200', slug: 'mainboard-xr-200', status: 'drafting', organization_id: 'o', created_at: '', updated_at: '' }
    store.draftName = 'Mainboard XR-200'
    store.draftSlug = 'mainboard-xr-200'
    store.assets = {
      bom: fakeAsset('bom', 188_416),
      golden_top: fakeAsset('golden_top', 4_404_019),
      drawing: fakeAsset('drawing', 1_887_436),
    }
    store.bomItems = SAMPLE_BOM
    await jumpTo(wrapper, 4)
    expect(wrapper.findAll('[data-testid="wizard-review-row"]').length).toBeGreaterThanOrEqual(4)
    expect(wrapper.find('[data-testid="wizard-what-next"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="wizard-create"]').exists()).toBe(true)
  })

  it('review Edit button jumps back to the matching step', async () => {
    const { wrapper } = await mountWizard()
    const store = useWizardStore()
    store.project = { id: 'p1', name: 'B', slug: 'b', status: 'drafting', organization_id: 'o', created_at: '', updated_at: '' }
    store.draftName = 'B'
    store.draftSlug = 'b'
    await jumpTo(wrapper, 4)
    await wrapper.get('[data-testid="wizard-edit-0"]').trigger('click')
    await nextTick()
    expect(store.stepIndex).toBe(0)
  })
})
