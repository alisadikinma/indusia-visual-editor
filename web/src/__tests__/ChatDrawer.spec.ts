import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import ChatDrawer from "../components/ChatDrawer.vue";
import { useChatStore } from "../stores/chat";

// Vitest's jsdom doesn't ship EventSource. Stub a minimal one whose
// `dispatchMessage()` simulates an incoming SSE chunk.
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  dispatchMessage(payload: object) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
  dispatchError() {
    this.onerror?.(new Event("error"));
  }
}

(globalThis as unknown as { EventSource: typeof FakeEventSource }).EventSource =
  FakeEventSource;

const PROJECT_ID = "11111111-1111-1111-1111-111111111111";
const SESSION_ID = "22222222-2222-2222-2222-222222222222";

describe("ChatDrawer", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    FakeEventSource.instances.length = 0;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the floating toggle button and hides the panel until clicked", async () => {
    const store = useChatStore();
    vi.spyOn(store, "openSession").mockResolvedValue();

    const wrapper = mount(ChatDrawer, {
      props: { projectId: PROJECT_ID },
    });
    expect(wrapper.find('[data-testid="chat-toggle"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="chat-panel"]').exists()).toBe(false);

    await wrapper.find('[data-testid="chat-toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="chat-panel"]').exists()).toBe(true);
    expect(store.openSession).toHaveBeenCalledWith(PROJECT_ID);
  });

  it("renders user message right-aligned and assistant message left-aligned", async () => {
    const store = useChatStore();
    store.sessionId = SESSION_ID;
    store.messages = [
      { role: "user", content: "C4 false positive?" },
      { role: "assistant", content: "Coba tweak threshold ke 0.85." },
    ];

    const wrapper = mount(ChatDrawer, {
      props: { projectId: PROJECT_ID },
    });
    await wrapper.find('[data-testid="chat-toggle"]').trigger("click");

    const userBubble = wrapper.find('[data-testid="msg-user"]');
    const assistantBubble = wrapper.find('[data-testid="msg-assistant"]');
    expect(userBubble.text()).toContain("C4 false positive?");
    expect(assistantBubble.text()).toContain("Coba tweak threshold");
    // Tailwind: user bubble aligns end, assistant aligns start.
    expect(userBubble.classes().some((c) => c.includes("self-end"))).toBe(true);
    expect(assistantBubble.classes().some((c) => c.includes("self-start"))).toBe(
      true,
    );
  });

  it("calls store.sendMessage when the user submits the input", async () => {
    const store = useChatStore();
    store.sessionId = SESSION_ID;
    const sendSpy = vi.spyOn(store, "sendMessage").mockResolvedValue();

    const wrapper = mount(ChatDrawer, {
      props: { projectId: PROJECT_ID },
    });
    await wrapper.find('[data-testid="chat-toggle"]').trigger("click");

    const input = wrapper.find('[data-testid="chat-input"]');
    await input.setValue("kenapa training run gagal?");
    await wrapper.find('[data-testid="chat-form"]').trigger("submit.prevent");
    await flushPromises();

    expect(sendSpy).toHaveBeenCalledOnce();
    expect(sendSpy).toHaveBeenCalledWith("kenapa training run gagal?");
  });

  it("shows a typing indicator while the store is streaming", async () => {
    const store = useChatStore();
    store.sessionId = SESSION_ID;
    store.streaming = true;

    const wrapper = mount(ChatDrawer, {
      props: { projectId: PROJECT_ID },
    });
    await wrapper.find('[data-testid="chat-toggle"]').trigger("click");

    expect(wrapper.find('[data-testid="typing-indicator"]').exists()).toBe(
      true,
    );
  });
});
