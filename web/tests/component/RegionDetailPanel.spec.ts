import { describe, expect, it, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import RegionDetailPanel from '@/components/labeling/RegionDetailPanel.vue'

const REGION = {
  id: 'dKfDULhmIx',
  results: [
    {
      type: 'rectanglelabels',
      value: {
        x: 46.929,
        y: 53.372,
        width: 8.706,
        height: 6.225,
        rotation: 0,
        rectanglelabels: ['R6'],
      },
    },
  ],
}

describe('RegionDetailPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the empty state with no region selected', () => {
    const w = mount(RegionDetailPanel, { props: { region: null } })
    expect(w.find('[data-testid="region-empty"]').exists()).toBe(true)
    expect(w.find('[data-testid="region-geometry"]').exists()).toBe(false)
  })

  it('renders Info/History tabs, geometry, criteria and action buttons', () => {
    const w = mount(RegionDetailPanel, { props: { region: REGION } })
    expect(w.find('[data-testid="region-tab-info"]').exists()).toBe(true)
    expect(w.find('[data-testid="region-tab-history"]').exists()).toBe(true)
    const geo = w.get('[data-testid="region-geometry"]').text()
    expect(geo).toContain('46.93')
    expect(geo).toContain('R6')
    // 8 defect-criteria checkboxes
    expect(w.findAll('[data-testid="region-criteria"] input[type="checkbox"]')).toHaveLength(8)
    // 4 action buttons
    for (const a of ['relate', 'copy', 'visible', 'delete']) {
      expect(w.find(`[data-testid="region-action-${a}"]`).exists()).toBe(true)
    }
  })

  it('emits applyCriteria with the ticked criteria', async () => {
    const w = mount(RegionDetailPanel, { props: { region: REGION } })
    const boxes = w.findAll('[data-testid="region-criteria"] input[type="checkbox"]')
    await boxes[0].setValue(true)
    await w.get('[data-testid="region-apply"]').trigger('click')
    const emitted = w.emitted('applyCriteria')
    expect(emitted).toBeTruthy()
    expect((emitted![0][0] as string[]).length).toBe(1)
  })

  it('switches to the History tab', async () => {
    const w = mount(RegionDetailPanel, { props: { region: REGION } })
    await w.get('[data-testid="region-tab-history"]').trigger('click')
    expect(w.find('[data-testid="region-history"]').exists()).toBe(true)
  })
})
