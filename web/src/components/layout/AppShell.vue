<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import AppTopBar from './AppTopBar.vue'
import ChatDrawer from '@/components/overlays/ChatDrawer.vue'
import ToastStack from '@/components/overlays/ToastStack.vue'
</script>

<template>
  <div
    data-testid="app-shell"
    class="min-h-screen flex bg-surface-sunken text-ink-900 font-sans"
  >
    <AppSidebar />
    <div class="flex-1 flex flex-col min-w-0">
      <AppTopBar />
      <main data-testid="app-main" class="flex-1 overflow-y-auto">
        <slot />
      </main>
    </div>
    <ChatDrawer />
    <ToastStack />
  </div>
</template>
