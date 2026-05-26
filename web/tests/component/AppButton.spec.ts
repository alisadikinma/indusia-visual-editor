import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppButton from '@/components/primitives/AppButton.vue'

describe('AppButton', () => {
  it('renders slot content', () => {
    const wrapper = mount(AppButton, { slots: { default: 'Save' } })
    expect(wrapper.text()).toBe('Save')
  })

  it('respects disabled prop', () => {
    const wrapper = mount(AppButton, { props: { disabled: true } })
    expect(wrapper.attributes('disabled')).toBeDefined()
  })

  it('applies primary classes by default', () => {
    const wrapper = mount(AppButton)
    expect(wrapper.classes().some((c) => c.includes('primary'))).toBe(true)
  })
})
