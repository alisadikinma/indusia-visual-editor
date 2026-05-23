import { defineStore } from "pinia";

import {
  createSession as apiCreateSession,
  streamReply as apiStreamReply,
  type ChatTurn,
} from "../api/chat";

type State = {
  projectId: string | null;
  sessionId: string | null;
  messages: ChatTurn[];
  streaming: boolean;
  error: string | null;
};

function extractErrorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  const respMsg = (e as {
    response?: { data?: { message?: string } };
  }).response?.data?.message;
  if (typeof respMsg === "string" && respMsg.length > 0) return respMsg;
  return "Terjadi kesalahan saat chat.";
}

export const useChatStore = defineStore("chat", {
  state: (): State => ({
    projectId: null,
    sessionId: null,
    messages: [],
    streaming: false,
    error: null,
  }),
  actions: {
    async openSession(projectId: string) {
      this.projectId = projectId;
      this.error = null;
      try {
        const sess = await apiCreateSession(projectId);
        this.sessionId = sess.id;
        this.messages = sess.messages_json;
      } catch (e) {
        this.error = extractErrorMessage(e);
      }
    },
    async sendMessage(userMessage: string) {
      if (this.sessionId === null) {
        this.error = "Sesi chat belum dibuka.";
        return;
      }
      this.messages.push({ role: "user", content: userMessage });
      // Tracking the assistant slot lets template render the in-progress
      // bubble live as deltas arrive without scattering reactivity hacks.
      const assistantIdx = this.messages.push({
        role: "assistant",
        content: "",
      }) - 1;
      this.streaming = true;
      this.error = null;

      try {
        for await (const frame of apiStreamReply(this.sessionId, userMessage)) {
          if (frame.delta) {
            this.messages[assistantIdx].content += frame.delta;
          } else if (frame.event === "error") {
            this.error = frame.error ?? "Stream error.";
          }
        }
      } catch (e) {
        this.error = extractErrorMessage(e);
      } finally {
        this.streaming = false;
      }
    },
    reset() {
      this.projectId = null;
      this.sessionId = null;
      this.messages = [];
      this.streaming = false;
      this.error = null;
    },
  },
});
