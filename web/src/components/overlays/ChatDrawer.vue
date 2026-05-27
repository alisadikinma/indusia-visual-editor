<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useChatStore } from '@/stores/chat'

const { t } = useI18n()
const chat = useChatStore()
const route = useRoute()

const inputText = ref('')
const scrollEl = ref<HTMLDivElement | null>(null)

const projectIdFromRoute = computed(() => {
  const id = route.params.id
  return typeof id === 'string' && id && id !== 'new' ? id : null
})

const canChat = computed(() => projectIdFromRoute.value != null)

watch(
  () => chat.drawerOpen,
  async (open) => {
    if (!open) return
    if (projectIdFromRoute.value) {
      await chat.ensureSession(projectIdFromRoute.value)
    }
    await nextTick()
    scrollToBottom()
  },
)

watch(
  () => chat.messages.length,
  async () => {
    await nextTick()
    scrollToBottom()
  },
)

function scrollToBottom() {
  if (!scrollEl.value) return
  scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

async function submit() {
  const text = inputText.value.trim()
  if (!text || chat.streaming) return
  inputText.value = ''
  await chat.sendMessage(text)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <!-- Toggle button -->
  <button
    type="button"
    class="fixed bottom-6 right-6 z-40 h-12 w-12 rounded-full bg-engineer-700 text-white shadow-pop hover:bg-engineer-800 transition grid place-items-center font-mono text-sm"
    :aria-label="t('chat.toggle')"
    @click="chat.toggleDrawer()"
  >
    ?
  </button>

  <!-- Backdrop -->
  <transition
    enter-active-class="transition"
    enter-from-class="opacity-0"
    leave-active-class="transition"
    leave-to-class="opacity-0"
  >
    <div
      v-if="chat.drawerOpen"
      class="fixed inset-0 bg-ink-900/40 backdrop-blur-sm z-40"
      @click="chat.closeDrawer()"
    />
  </transition>

  <!-- Panel -->
  <transition
    enter-active-class="transition transform"
    enter-from-class="translate-x-full"
    leave-active-class="transition transform"
    leave-to-class="translate-x-full"
  >
    <aside
      v-if="chat.drawerOpen"
      class="fixed top-0 right-0 bottom-0 z-50 w-full max-w-md bg-white shadow-pop flex flex-col"
    >
      <header class="flex items-center justify-between px-5 py-4 border-b border-ink-200">
        <div>
          <p class="text-xs font-mono uppercase tracking-wider text-ink-500">
            {{ t('chat.kicker') }}
          </p>
          <h2 class="text-base font-semibold text-ink-900">{{ t('chat.title') }}</h2>
        </div>
        <button
          type="button"
          class="h-8 w-8 grid place-items-center rounded-md text-ink-500 hover:bg-ink-100"
          @click="chat.closeDrawer()"
        >
          ✕
        </button>
      </header>

      <div
        v-if="!canChat"
        class="flex-1 grid place-items-center p-8 text-center text-sm text-ink-500"
      >
        {{ t('chat.openProjectFirst') }}
      </div>

      <div
        v-else
        ref="scrollEl"
        class="flex-1 overflow-y-auto px-5 py-4 space-y-3"
      >
        <p v-if="chat.messages.length === 0" class="text-sm text-ink-500 text-center py-8">
          {{ t('chat.empty') }}
        </p>
        <div
          v-for="(m, i) in chat.messages"
          :key="i"
          class="flex"
          :class="m.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap"
            :class="
              m.role === 'user'
                ? 'bg-primary-700 text-white'
                : 'bg-ink-100 text-ink-900'
            "
          >
            <p v-if="m.role === 'assistant' && !m.content && chat.streaming" class="text-ink-500">
              <span class="inline-flex gap-1">
                <span class="h-1.5 w-1.5 rounded-full bg-ink-400 animate-bounce" />
                <span class="h-1.5 w-1.5 rounded-full bg-ink-400 animate-bounce [animation-delay:0.15s]" />
                <span class="h-1.5 w-1.5 rounded-full bg-ink-400 animate-bounce [animation-delay:0.3s]" />
              </span>
            </p>
            <p v-else>{{ m.content }}</p>
          </div>
        </div>
        <p v-if="chat.error" class="text-xs text-red-700 bg-red-50 border border-red-200 rounded-md p-2">
          {{ chat.error }}
        </p>
      </div>

      <footer v-if="canChat" class="border-t border-ink-200 p-3">
        <textarea
          v-model="inputText"
          rows="2"
          :placeholder="t('chat.placeholder')"
          :disabled="chat.streaming"
          class="w-full resize-none rounded-lg border border-ink-200 px-3 py-2 text-sm focus:border-primary-600 focus:ring-2 focus:ring-primary-100 outline-none transition"
          @keydown="onKeydown"
        />
        <div class="flex items-center justify-between mt-2">
          <p class="text-[11px] font-mono text-ink-500">
            {{ t('chat.shortcut') }}
          </p>
          <button
            type="button"
            class="h-8 px-4 rounded-md bg-primary-700 hover:bg-primary-800 text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition"
            :disabled="!inputText.trim() || chat.streaming"
            @click="submit"
          >
            {{ chat.streaming ? t('common.loading') : t('chat.send') }}
          </button>
        </div>
      </footer>
    </aside>
  </transition>
</template>
