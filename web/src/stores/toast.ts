import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastVariant = 'success' | 'warning' | 'error'

export interface Toast {
  id: string
  variant: ToastVariant
  title: string
  body?: string
}

const DEFAULT_TTL_MS = 4000

export const useToastStore = defineStore('toast', () => {
  const items = ref<Toast[]>([])

  function push(variant: ToastVariant, title: string, body?: string, ttlMs = DEFAULT_TTL_MS) {
    const id = crypto.randomUUID()
    items.value = [...items.value, { id, variant, title, body }]
    if (ttlMs > 0) {
      window.setTimeout(() => dismiss(id), ttlMs)
    }
    return id
  }

  function success(title: string, body?: string) {
    return push('success', title, body)
  }
  function warning(title: string, body?: string) {
    return push('warning', title, body)
  }
  function error(title: string, body?: string) {
    return push('error', title, body, 6000)
  }

  function dismiss(id: string) {
    items.value = items.value.filter((t) => t.id !== id)
  }

  function clear() {
    items.value = []
  }

  return { items, push, success, warning, error, dismiss, clear }
})
