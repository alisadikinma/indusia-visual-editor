import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

import LSFEmbed from "../components/LSFEmbed.vue";

interface LsfInstanceOptions {
  config: string;
  task: unknown;
  interfaces?: string[];
  reactVersion?: string;
  onLabelStudioLoad?: (ls: unknown) => void;
  onSubmitAnnotation?: (ls: unknown, ann: unknown) => void;
  onUpdateAnnotation?: (ls: unknown, ann: unknown) => void;
  onSkipTask?: (ls: unknown) => void;
}

class MockLabelStudio {
  static lastCall: { target: unknown; options: LsfInstanceOptions } | null = null;
  destroyed = false;
  options: LsfInstanceOptions;

  constructor(target: unknown, options: LsfInstanceOptions) {
    MockLabelStudio.lastCall = { target, options };
    this.options = options;
    // Mimic LSF's async load.
    queueMicrotask(() => options.onLabelStudioLoad?.(this));
  }

  destroy() {
    this.destroyed = true;
  }
}

const baseConfig =
  '<View><Image name="image" value="$image" />' +
  '<RectangleLabels name="label" toName="image"><Label value="R1" /></RectangleLabels>' +
  "</View>";

const baseTask = {
  id: 1,
  data: { image: "/api/projects/abc/assets/xyz/binary" },
  predictions: [],
  annotations: [],
};

describe("LSFEmbed", () => {
  beforeEach(() => {
    MockLabelStudio.lastCall = null;
    vi.stubGlobal("LabelStudio", MockLabelStudio);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("instantiates LabelStudio with reactVersion v18 and the passed config + task", async () => {
    const wrapper = mount(LSFEmbed, {
      props: { config: baseConfig, task: baseTask },
      attachTo: document.body,
    });
    await flushPromises();

    expect(MockLabelStudio.lastCall).not.toBeNull();
    const { options, target } = MockLabelStudio.lastCall!;
    expect(options.reactVersion).toBe("v18");
    expect(options.config).toBe(baseConfig);
    expect(options.task).toEqual(baseTask);
    // Target must be a real DOM node (LSF requires it; passing a CSS
    // selector breaks when the wrapper unmounts before the constructor).
    expect(target).toBeInstanceOf(HTMLElement);

    wrapper.unmount();
  });

  it("emits submit when LSF invokes onSubmitAnnotation", async () => {
    const wrapper = mount(LSFEmbed, {
      props: { config: baseConfig, task: baseTask },
      attachTo: document.body,
    });
    await flushPromises();

    const { options } = MockLabelStudio.lastCall!;
    const fakeAnnotation = { serializeAnnotation: () => [{ id: "r1" }] };
    options.onSubmitAnnotation?.(null, fakeAnnotation);
    await flushPromises();

    const emitted = wrapper.emitted("submit");
    expect(emitted).toBeDefined();
    expect(emitted!.length).toBe(1);
    expect(emitted![0][0]).toEqual({ result: [{ id: "r1" }] });

    wrapper.unmount();
  });

  it("emits update when LSF invokes onUpdateAnnotation", async () => {
    const wrapper = mount(LSFEmbed, {
      props: { config: baseConfig, task: baseTask },
      attachTo: document.body,
    });
    await flushPromises();

    const { options } = MockLabelStudio.lastCall!;
    options.onUpdateAnnotation?.(null, {
      serializeAnnotation: () => [{ id: "r2" }],
    });
    await flushPromises();

    const emitted = wrapper.emitted("update");
    expect(emitted).toBeDefined();
    expect(emitted![0][0]).toEqual({ result: [{ id: "r2" }] });

    wrapper.unmount();
  });

  it("destroys the LSF instance on unmount", async () => {
    const wrapper = mount(LSFEmbed, {
      props: { config: baseConfig, task: baseTask },
      attachTo: document.body,
    });
    await flushPromises();

    const instance = MockLabelStudio.lastCall!.target as unknown;
    void instance;
    const ls = (MockLabelStudio.lastCall as unknown as {
      options: { onLabelStudioLoad: (ls: MockLabelStudio) => void };
    }).options;
    void ls;

    // The component holds the MockLabelStudio instance internally and must
    // call .destroy() during unmount. We assert by inspecting the most
    // recent constructed mock.
    const lastInstance = (globalThis as { LabelStudio?: typeof MockLabelStudio })
      .LabelStudio as typeof MockLabelStudio;
    // The instance is unique per mount — re-grab it via constructor proxy.
    // Use vi spy on prototype.destroy to assert call.
    const destroySpy = vi.spyOn(lastInstance.prototype, "destroy");

    wrapper.unmount();
    expect(destroySpy).toHaveBeenCalled();
  });

  it("emits load-error when window.LabelStudio is missing", async () => {
    vi.unstubAllGlobals(); // remove the mock for this test only
    vi.useFakeTimers();

    const wrapper = mount(LSFEmbed, {
      props: { config: baseConfig, task: baseTask, loadTimeoutMs: 200 },
      attachTo: document.body,
    });

    // Advance past the polling window.
    await vi.advanceTimersByTimeAsync(250);

    const errors = wrapper.emitted("load-error");
    expect(errors).toBeDefined();
    expect(String(errors![0][0])).toMatch(/LabelStudio/i);

    wrapper.unmount();
  });
});
