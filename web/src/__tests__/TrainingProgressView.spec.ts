import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";
import { nextTick } from "vue";

import TrainingProgressView from "../views/TrainingProgressView.vue";

// Minimal in-process EventSource double. The view opens an EventSource at
// the stream URL on mount and reads progress events; the test drives the
// `onmessage` and `onerror` handlers manually so we can simulate the
// upstream SSE without a network round-trip.
class FakeEventSource {
  static lastInstance: FakeEventSource | null = null;
  static lastUrl: string | null = null;
  url: string;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.lastUrl = url;
    FakeEventSource.lastInstance = this;
  }

  close() {
    this.closed = true;
  }

  emit(payload: object) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

function buildRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "dashboard", component: { template: "<div />" } },
      {
        path: "/projects/:id/training/:runId",
        name: "training-progress",
        component: TrainingProgressView,
      },
    ],
  });
  return router;
}

describe("TrainingProgressView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    FakeEventSource.lastInstance = null;
    FakeEventSource.lastUrl = null;
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens an EventSource on mount and updates DOM as events arrive", async () => {
    const router = buildRouter();
    await router.push("/projects/pid-1/training/run-xyz");
    await router.isReady();

    const wrapper = mount(TrainingProgressView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    expect(FakeEventSource.lastUrl).toContain("/api/training/run-xyz/stream");

    const es = FakeEventSource.lastInstance!;
    es.emit({ event: "running", epoch: 1, loss: 0.42 });
    await nextTick();
    expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
      "running",
    );
    expect(wrapper.html()).toContain("1"); // current epoch

    es.emit({ event: "epoch", epoch: 7, loss: 0.21, mAP: 0.81 });
    await nextTick();
    expect(wrapper.html()).toContain("7");

    es.emit({
      event: "succeeded",
      metrics: { mAP: 0.83, per_component_f1: { R1: 0.91 } },
    });
    await nextTick();
    expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
      "succeeded",
    );
    // Stream closed on terminal.
    expect(es.closed).toBe(true);
  });

  it("renders error message and closes stream on terminal failed event", async () => {
    const router = buildRouter();
    await router.push("/projects/pid-1/training/run-bad");
    await router.isReady();

    const wrapper = mount(TrainingProgressView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    const es = FakeEventSource.lastInstance!;
    es.emit({ event: "failed", error: "model crashed mid-epoch" });
    await nextTick();

    expect(wrapper.find('[data-testid="training-error"]').text()).toContain(
      "model crashed",
    );
    expect(wrapper.find('[data-testid="status-badge"]').text()).toContain(
      "failed",
    );
    expect(es.closed).toBe(true);
  });

  it("closes the EventSource on unmount", async () => {
    const router = buildRouter();
    await router.push("/projects/pid-1/training/run-cleanup");
    await router.isReady();

    const wrapper = mount(TrainingProgressView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    const es = FakeEventSource.lastInstance!;
    expect(es.closed).toBe(false);

    wrapper.unmount();
    expect(es.closed).toBe(true);
  });
});
