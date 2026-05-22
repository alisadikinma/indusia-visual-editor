import { describe, expect, it, beforeEach, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";

import PreLabelPanel from "../components/PreLabelPanel.vue";
import { useWizardStore } from "../stores/wizard";

vi.mock("../api/prelabel", () => ({
  runPreLabel: vi.fn(),
  getPreLabel: vi.fn(),
}));

describe("PreLabelPanel", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("renders empty state when no regions detected yet", () => {
    const wrapper = mount(PreLabelPanel, {
      props: { projectId: "pid-1", side: "top" },
    });
    expect(wrapper.find('[data-testid="prelabel-empty"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="prelabel-trigger-top"]').text()).toContain(
      "Jalankan",
    );
  });

  it("renders loading state while sideState.loading is true", async () => {
    const wrapper = mount(PreLabelPanel, {
      props: { projectId: "pid-1", side: "top" },
    });
    const store = useWizardStore();
    store.prelabel.top.loading = true;
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="prelabel-loading"]').exists()).toBe(true);
  });

  it("renders success with region count after run", async () => {
    const wrapper = mount(PreLabelPanel, {
      props: { projectId: "pid-1", side: "top" },
    });
    const store = useWizardStore();
    store.prelabel.top.regions = [
      { designator: "R1", bbox: [0, 0, 0.1, 0.1], confidence: 0.9, side: "top" },
      { designator: "C4", bbox: [0.2, 0.2, 0.1, 0.1], confidence: 0.8, side: "top" },
    ];
    await wrapper.vm.$nextTick();
    const success = wrapper.find('[data-testid="prelabel-success"]');
    expect(success.exists()).toBe(true);
    expect(success.text()).toContain("2");
  });

  it("renders error envelope on failure", async () => {
    const wrapper = mount(PreLabelPanel, {
      props: { projectId: "pid-1", side: "bottom" },
    });
    const store = useWizardStore();
    store.prelabel.bottom.error = "Ollama tidak bisa diakses";
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[data-testid="prelabel-error"]').text()).toContain(
      "Ollama",
    );
  });
});
