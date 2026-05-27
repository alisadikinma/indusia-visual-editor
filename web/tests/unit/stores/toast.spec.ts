import { describe, expect, it, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useToastStore } from '@/stores/toast'

describe('toast store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  it('pushes toast with variant + title', () => {
    const toast = useToastStore()
    toast.success('Saved')
    expect(toast.items.length).toBe(1)
    expect(toast.items[0].variant).toBe('success')
    expect(toast.items[0].title).toBe('Saved')
  })

  it('auto-dismisses success after default ttl', () => {
    const toast = useToastStore()
    toast.success('Saved')
    expect(toast.items.length).toBe(1)
    vi.advanceTimersByTime(4001)
    expect(toast.items.length).toBe(0)
  })

  it('error toast lasts longer (6s) than success', () => {
    const toast = useToastStore()
    toast.error('Boom')
    vi.advanceTimersByTime(4001)
    expect(toast.items.length).toBe(1)
    vi.advanceTimersByTime(2000)
    expect(toast.items.length).toBe(0)
  })

  it('dismiss removes a single toast by id', () => {
    const toast = useToastStore()
    const id1 = toast.success('A')
    toast.success('B')
    toast.dismiss(id1)
    expect(toast.items.length).toBe(1)
    expect(toast.items[0].title).toBe('B')
  })

  it('clear removes all', () => {
    const toast = useToastStore()
    toast.success('A')
    toast.warning('B')
    toast.error('C')
    expect(toast.items.length).toBe(3)
    toast.clear()
    expect(toast.items.length).toBe(0)
  })
})
