import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as chatApi from '@/api/chat'
import type { ChatMessage } from '@/api/chat'
import { useAuthStore } from './auth'

function extractMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { message?: string } }; message?: string }
  return e?.response?.data?.message ?? e?.message ?? fallback
}

export const useChatStore = defineStore('chat', () => {
  const drawerOpen = ref(false)
  const sessionId = ref<string | null>(null)
  const projectId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const error = ref<string | null>(null)

  const hasSession = computed(() => sessionId.value !== null)

  function openDrawer() {
    drawerOpen.value = true
  }
  function closeDrawer() {
    drawerOpen.value = false
  }
  function toggleDrawer() {
    drawerOpen.value = !drawerOpen.value
  }

  async function ensureSession(nextProjectId: string): Promise<void> {
    if (sessionId.value && projectId.value === nextProjectId) return
    error.value = null
    projectId.value = nextProjectId
    try {
      const sessions = await chatApi.listSessions(nextProjectId)
      const session =
        sessions[0] ?? (await chatApi.createSession(nextProjectId))
      sessionId.value = session.id
      messages.value = session.messages_json as ChatMessage[]
    } catch (err) {
      error.value = extractMessage(err, 'Failed to load chat session')
    }
  }

  async function sendMessage(userMessage: string): Promise<void> {
    if (!sessionId.value || streaming.value) return
    const auth = useAuthStore()
    const now = new Date().toISOString()
    messages.value = [
      ...messages.value,
      { role: 'user', content: userMessage, ts: now },
      { role: 'assistant', content: '', ts: now },
    ]
    streaming.value = true
    error.value = null
    try {
      const gen = chatApi.streamReply(sessionId.value, userMessage, auth.accessToken)
      for await (const frame of gen) {
        if (frame.delta) {
          // Append delta to the last (assistant) message.
          const last = messages.value[messages.value.length - 1]
          messages.value = [
            ...messages.value.slice(0, -1),
            { ...last, content: last.content + frame.delta },
          ]
        }
        if (frame.event === 'error') {
          error.value = frame.error ?? 'stream error'
          break
        }
        if (frame.event === 'done') break
      }
    } catch (err) {
      error.value = extractMessage(err, 'Chat stream failed')
    } finally {
      streaming.value = false
    }
  }

  function reset() {
    drawerOpen.value = false
    sessionId.value = null
    projectId.value = null
    messages.value = []
    streaming.value = false
    error.value = null
  }

  return {
    drawerOpen,
    sessionId,
    projectId,
    messages,
    streaming,
    error,
    hasSession,
    openDrawer,
    closeDrawer,
    toggleDrawer,
    ensureSession,
    sendMessage,
    reset,
  }
})
