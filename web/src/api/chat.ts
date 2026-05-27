import { apiClient } from './client'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  ts: string
}

export interface ChatSession {
  id: string
  project_id: string
  messages_json: ChatMessage[]
  created_at: string
  updated_at: string
}

interface Envelope<T> {
  status: boolean
  message: string
  data: T
}

export async function createSession(projectId: string): Promise<ChatSession> {
  const { data } = await apiClient.post<Envelope<ChatSession>>(
    `/projects/${projectId}/chat`,
    null,
  )
  return data.data
}

export async function listSessions(projectId: string): Promise<ChatSession[]> {
  const { data } = await apiClient.get<Envelope<ChatSession[]>>(
    `/projects/${projectId}/chat`,
  )
  return data.data
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  const { data } = await apiClient.get<Envelope<ChatSession>>(`/chat/${sessionId}`)
  return data.data
}

/**
 * Streams an assistant reply via `POST /api/chat/{session_id}/stream`.
 * EventSource cannot POST a body, so we manually parse a chunked SSE body
 * from fetch. Yields each `delta` text chunk; emits a final `event: done`
 * or `event: error` marker before completing.
 */
export async function* streamReply(
  sessionId: string,
  userMessage: string,
  accessToken: string | null,
): AsyncGenerator<{ delta?: string; event?: 'done' | 'error'; error?: string }> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  const resp = await fetch(`/api/chat/${sessionId}/stream`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: JSON.stringify({ user_message: userMessage }),
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`stream failed: HTTP ${resp.status}`)
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) return
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, idx).trim()
      buf = buf.slice(idx + 2)
      if (!block.startsWith('data:')) continue
      const json = block.slice(5).trim()
      try {
        yield JSON.parse(json)
      } catch {
        /* ignore malformed frame */
      }
    }
  }
}
