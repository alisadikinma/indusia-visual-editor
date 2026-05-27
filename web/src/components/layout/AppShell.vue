<script setup lang="ts">
import AppSidebar from './AppSidebar.vue'
import AppTopBar from './AppTopBar.vue'
import ChatDrawer from '@/components/overlays/ChatDrawer.vue'
import ToastStack from '@/components/overlays/ToastStack.vue'
</script>

<template>
  <div class="min-h-screen flex bg-ink-50 text-ink-900 font-sans">
    <AppSidebar />
    <div class="flex-1 flex flex-col min-w-0">
      <AppTopBar />
      <main class="flex-1 overflow-y-auto">
        <slot />
      </main>
    </div>
    <ChatDrawer />
    <ToastStack />
  </div>
</template>
