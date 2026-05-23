<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import ChatDrawer from "./components/ChatDrawer.vue";

const route = useRoute();

// The drawer only makes sense inside a project context — needs a project_id
// to spin up a chat_sessions row and feed the advisor with metrics/labels.
// The Dashboard route has no :id param, so we render nothing there.
const projectId = computed(() => {
  const raw = route.params.id;
  if (typeof raw === "string" && raw.length > 0) return raw;
  return null;
});
</script>

<template>
  <router-view />
  <ChatDrawer v-if="projectId !== null" :project-id="projectId" />
</template>
