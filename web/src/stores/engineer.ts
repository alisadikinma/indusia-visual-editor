import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'ive.engineer_mode'

export const useEngineerStore = defineStore('engineer', () => {
  const initial =
    typeof localStorage !== 'undefined' && localStorage.getItem(STORAGE_KEY) === 'true'
  const enabled = ref<boolean>(initial)

  watch(enabled, (next) => {
    if (typeof localStorage === 'undefined') return
    localStorage.setItem(STORAGE_KEY, String(next))
  })

  function toggle() {
    enabled.value = !enabled.value
  }

  return { enabled, toggle }
})
