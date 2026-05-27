<script setup lang="ts">
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()

const variantClass: Record<string, string> = {
  success: 'bg-primary-50 border-primary-200 text-primary-900',
  warning: 'bg-amber-50 border-amber-200 text-amber-900',
  error: 'bg-red-50 border-red-200 text-red-900',
}

const iconChar: Record<string, string> = {
  success: '✓',
  warning: '!',
  error: '✕',
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[60] flex flex-col gap-2 max-w-sm pointer-events-none">
    <transition-group
      enter-active-class="transition transform"
      enter-from-class="opacity-0 translate-x-4"
      leave-active-class="transition transform"
      leave-to-class="opacity-0 translate-x-4"
    >
      <div
        v-for="item in toast.items"
        :key="item.id"
        class="pointer-events-auto rounded-xl border shadow-pop px-4 py-3 flex gap-3 items-start min-w-[280px]"
        :class="variantClass[item.variant]"
        role="status"
      >
        <span class="h-5 w-5 grid place-items-center rounded-full text-xs font-mono font-semibold shrink-0">
          {{ iconChar[item.variant] }}
        </span>
        <div class="flex-1 min-w-0">
          <p class="text-sm font-semibold">{{ item.title }}</p>
          <p v-if="item.body" class="text-xs opacity-90 mt-0.5">{{ item.body }}</p>
        </div>
        <button
          type="button"
          class="h-5 w-5 grid place-items-center text-xs opacity-60 hover:opacity-100 transition"
          @click="toast.dismiss(item.id)"
        >
          ✕
        </button>
      </div>
    </transition-group>
  </div>
</template>
