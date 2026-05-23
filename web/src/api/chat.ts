import { api, type ApiEnvelope } from "./client";

export type ChatTurn = {
  role: "user" | "assistant" | "system";
  content: string;
  ts?: string;
};

export type ChatSession = {
  id: string;
  project_id: string;
  messages_json: ChatTurn[];
  created_at: string;
  updated_at: string;
};

export async function createSession(projectId: string): Promise<ChatSession> {
  const r = await api.post<ApiEnvelope<ChatSession>>(
    `/api/projects/${projectId}/chat`,
  );
  return r.data.data;
}

export async function listSessions(projectId: string): Promise<ChatSession[]> {
  const r = await api.get<ApiEnvelope<ChatSession[]>>(
    `/api/projects/${projectId}/chat`,
  );
  return r.data.data;
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  const r = await api.get<ApiEnvelope<ChatSession>>(`/api/chat/${sessionId}`);
  return r.data.data;
}

/**
 * The backend's POST /api/chat/{session_id}/stream is an SSE endpoint —
 * one `data:` line per chunk. The browser's `EventSource` only supports
 * GET, so we use fetch + ReadableStream to send the user message in the
 * request body and parse SSE manually. Yields {delta} or {event} frames.
 */
export async function* streamReply(
  sessionId: string,
  userMessage: string,
  signal?: AbortSignal,
): AsyncGenerator<{ delta?: string; event?: string; error?: string }, void> {
  const baseURL =
    (api.defaults.baseURL as string | undefined) ?? "http://localhost:8002";
  const response = await fetch(`${baseURL}/api/chat/${sessionId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ user_message: userMessage }),
    signal,
  });
  if (!response.ok || response.body === null) {
    throw new Error(`chat stream HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nlIdx: number;
    while ((nlIdx = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nlIdx).trimEnd();
      buffer = buffer.slice(nlIdx + 1);
      if (!line.startsWith("data:")) continue;
      const payload = line.slice("data:".length).trim();
      if (!payload) continue;
      try {
        yield JSON.parse(payload);
      } catch {
        // Skip malformed SSE frames silently — upstream will emit a
        // canonical {event:'error'} terminal if it intends to fail.
      }
    }
  }
}
