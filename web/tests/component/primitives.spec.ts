import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppCard from '@/components/primitives/AppCard.vue'
import AppStepper from '@/components/primitives/AppStepper.vue'
import AppBadge from '@/components/primitives/AppBadge.vue'
import IconButton from '@/components/primitives/IconButton.vue'
import FormField from '@/components/primitives/FormField.vue'
import EmptyState from '@/components/primitives/EmptyState.vue'
import AppPill from '@/components/primitives/AppPill.vue'
import AppDivider from '@/components/primitives/AppDivider.vue'

describe('AppCard', () => {
  it('renders slot and exposes data-testid root', () => {
    const w = mount(AppCard, { slots: { default: 'Content' } })
    expect(w.text()).toContain('Content')
    expect(w.attributes('data-testid')).toBe('app-card')
  })

  it('applies raised variant class', () => {
    const w = mount(AppCard, { props: { variant: 'raised' } })
    expect(w.classes().some((c) => c.includes('surface') || c.includes('raised') || c.includes('bg-surface-raised'))).toBe(true)
  })
})

describe('AppStepper', () => {
  it('renders one node per step with data-testid', () => {
    const steps = [
      { id: 'a', label: 'Basics' },
      { id: 'b', label: 'BOM' },
      { id: 'c', label: 'Review' },
    ]
    const w = mount(AppStepper, { props: { steps, current: 1 } })
    expect(w.attributes('data-testid')).toBe('app-stepper')
    for (const s of steps) {
      expect(w.find(`[data-testid="stepper-node-${s.id}"]`).exists()).toBe(true)
    }
  })

  it('marks current step as active', () => {
    const steps = [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }]
    const w = mount(AppStepper, { props: { steps, current: 0 } })
    const a = w.find('[data-testid="stepper-node-a"]')
    expect(a.attributes('data-state')).toBe('active')
  })
})

describe('AppBadge', () => {
  it('renders slot and exposes data-testid', () => {
    const w = mount(AppBadge, { slots: { default: 'PASS' } })
    expect(w.text()).toBe('PASS')
    expect(w.attributes('data-testid')).toBe('app-badge')
  })

  it('applies danger variant class', () => {
    const w = mount(AppBadge, { props: { variant: 'danger' } })
    expect(w.attributes('data-variant')).toBe('danger')
  })
})

describe('IconButton', () => {
  it('renders icon slot and is a button', () => {
    const w = mount(IconButton, {
      attrs: { 'aria-label': 'Close' },
      slots: { default: '<svg data-icon />' },
    })
    expect(w.element.tagName).toBe('BUTTON')
    expect(w.attributes('aria-label')).toBe('Close')
    expect(w.attributes('data-testid')).toBe('icon-button')
  })

  it('honors disabled prop', () => {
    const w = mount(IconButton, { props: { disabled: true } })
    expect(w.attributes('disabled')).toBeDefined()
  })
})

describe('FormField', () => {
  it('renders label and input slot, wires id to for', () => {
    const w = mount(FormField, {
      props: { id: 'email', label: 'Email' },
      slots: { default: '<input id="email" />' },
    })
    expect(w.attributes('data-testid')).toBe('form-field')
    expect(w.find('label').attributes('for')).toBe('email')
    expect(w.text()).toContain('Email')
  })

  it('renders error message and marks invalid', () => {
    const w = mount(FormField, {
      props: { id: 'x', label: 'X', error: 'Required' },
      slots: { default: '<input id="x" />' },
    })
    expect(w.text()).toContain('Required')
    expect(w.attributes('data-invalid')).toBe('true')
  })
})

describe('EmptyState', () => {
  it('renders title and description', () => {
    const w = mount(EmptyState, {
      props: { title: 'Belum ada project', description: 'Buat project pertama untuk mulai.' },
    })
    expect(w.attributes('data-testid')).toBe('empty-state')
    expect(w.text()).toContain('Belum ada project')
    expect(w.text()).toContain('Buat project pertama')
  })

  it('renders action slot', () => {
    const w = mount(EmptyState, {
      props: { title: 'X' },
      slots: { action: '<button>Create</button>' },
    })
    expect(w.find('button').text()).toBe('Create')
  })
})

describe('AppPill', () => {
  it('emits click and toggles selected attr', async () => {
    const w = mount(AppPill, { props: { selected: false }, slots: { default: 'EN' } })
    expect(w.attributes('data-testid')).toBe('app-pill')
    expect(w.attributes('data-selected')).toBe('false')
    await w.trigger('click')
    expect(w.emitted('click')).toBeTruthy()
  })

  it('marks selected when prop is true', () => {
    const w = mount(AppPill, { props: { selected: true }, slots: { default: 'ID' } })
    expect(w.attributes('data-selected')).toBe('true')
  })
})

describe('AppDivider', () => {
  it('renders horizontal by default', () => {
    const w = mount(AppDivider)
    expect(w.attributes('data-testid')).toBe('app-divider')
    expect(w.attributes('data-orientation')).toBe('horizontal')
  })

  it('renders vertical when prop set', () => {
    const w = mount(AppDivider, { props: { orientation: 'vertical' } })
    expect(w.attributes('data-orientation')).toBe('vertical')
  })

  it('renders label slot for OR-style divider', () => {
    const w = mount(AppDivider, { props: { label: 'OR' } })
    expect(w.text()).toContain('OR')
  })
})
