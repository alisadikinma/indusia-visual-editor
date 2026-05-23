<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import { useChatStore } from "../stores/chat";

const props = defineProps<{ projectId: string }>();

const store = useChatStore();
const isOpen = ref(false);
const draft = ref("");
const messageList = ref<HTMLElement | null>(null);

const messages = computed(() => store.messages);

async function toggle() {
  isOpen.value = !isOpen.value;
  if (isOpen.value && store.sessionId === null) {
    await store.openSession(props.projectId);
  }
}

async function submit() {
  const text = draft.value.trim();
  if (text.length === 0 || store.streaming) return;
  draft.value = "";
  await store.sendMessage(text);
}

watch(
  () => store.messages.length,
  async () => {
    await nextTick();
    if (messageList.value !== null) {
      messageList.value.scrollTop = messageList.value.scrollHeight;
    }
  },
);
</script>

<template>
  <div>
    <button
      type="button"
      data-testid="chat-toggle"
      class="fixed bottom-6 right-6 z-30 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-text-on-primary shadow-lg transition-colors duration-150 hover:bg-primary-hover"
      :aria-label="isOpen ? 'Tutup chat advisor' : 'Buka chat advisor'"
      @click="toggle"
    >
      <span class="font-semibold">{{ isOpen ? "×" : "?" }}</span>
    </button>

    <aside
      v-if="isOpen"
      data-testid="chat-panel"
      class="fixed bottom-24 right-6 z-30 flex h-[32rem] w-96 flex-col rounded-md border border-border-default bg-bg-elevated shadow-xl"
      role="dialog"
      aria-label="Chat advisor inspeksi PCB"
    >
      <header class="border-b border-border-default px-4 py-3">
        <h2 class="font-sans text-sm font-semibold text-text-primary">
          Advisor Inspeksi
        </h2>
        <p class="text-xs text-text-secondary">
          Tanya apa saja soal training run, defect rate, atau threshold.
        </p>
      </header>

      <div
        ref="messageList"
        class="flex flex-1 flex-col gap-2 overflow-y-auto px-4 py-3"
      >
        <p
          v-if="messages.length === 0"
          class="text-center text-xs text-text-tertiary"
        >
          Belum ada percakapan. Ketik pertanyaan di bawah.
        </p>

        <template v-for="(msg, idx) in messages" :key="idx">
          <div
            v-if="msg.role === 'user'"
            data-testid="msg-user"
            class="max-w-[80%] self-end rounded-md bg-primary px-3 py-2 text-sm text-text-on-primary"
          >
            {{ msg.content }}
          </div>
          <div
            v-else-if="msg.role === 'assistant'"
            data-testid="msg-assistant"
            class="max-w-[80%] self-start rounded-md bg-bg-deep px-3 py-2 text-sm text-text-primary"
          >
            {{ msg.content }}
          </div>
        </template>

        <p
          v-if="store.streaming"
          data-testid="typing-indicator"
          class="self-start text-xs italic text-text-tertiary"
        >
          Advisor sedang mengetik...
        </p>

        <p
          v-if="store.error"
          class="self-center text-xs text-danger"
          role="alert"
        >
          {{ store.error }}
        </p>
      </div>

      <form
        data-testid="chat-form"
        class="border-t border-border-default p-3"
        @submit.prevent="submit"
      >
        <div class="flex gap-2">
          <input
            v-model="draft"
            data-testid="chat-input"
            type="text"
            placeholder="C4 false-positive di line 3, kenapa?"
            class="flex-1 rounded border border-border-default bg-bg-deep px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-primary focus:outline-none"
            :disabled="store.streaming"
          />
          <button
            type="submit"
            class="rounded bg-primary px-3 py-2 text-xs font-semibold uppercase tracking-wide text-text-on-primary transition-colors duration-150 hover:bg-primary-hover disabled:opacity-50"
            :disabled="store.streaming || draft.trim().length === 0"
          >
            Kirim
          </button>
        </div>
      </form>
    </aside>
  </div>
</template>
