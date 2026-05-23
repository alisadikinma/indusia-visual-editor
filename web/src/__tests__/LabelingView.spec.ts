import { describe, expect, it, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

import LabelingView from "../views/LabelingView.vue";

vi.mock("../api/labels", () => ({
  getTask: vi.fn(),
  submitLabels: vi.fn(),
  absoluteImageUrl: (rel: string) => `http://localhost:8002${rel}`,
}));

vi.mock("../components/LSFEmbed.vue", () => ({
  default: {
    name: "LSFEmbedStub",
    props: ["config", "task", "interfaces"],
    emits: ["submit", "update", "ready", "load-error"],
    template: '<div data-testid="lsf-stub" :data-side="task?.data?.image"></div>',
  },
}));

import { getTask, submitLabels } from "../api/labels";

const baseTaskResp = (side: "top" | "bottom" = "top") => ({
  config: "<View><Image /></View>",
  task: {
    id: 1,
    data: { image: `/api/projects/pid-1/assets/asset-${side}/binary` },
    predictions: [],
    annotations: [],
  },
  side,
  designator_count: 2,
});

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "home", component: { template: "<div />" } },
      { path: "/projects/:id/labeling", name: "labeling", component: LabelingView },
    ],
  });
}

describe("LabelingView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    (getTask as unknown as ReturnType<typeof vi.fn>).mockReset();
    (submitLabels as unknown as ReturnType<typeof vi.fn>).mockReset();
  });

  it("fetches the task on mount and passes config+task to LSFEmbed", async () => {
    (getTask as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      baseTaskResp("top"),
    );

    const router = makeRouter();
    await router.push("/projects/pid-1/labeling");
    const wrapper = mount(LabelingView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    expect(getTask).toHaveBeenCalledWith("pid-1", "top");
    expect(wrapper.find('[data-testid="lsf-stub"]').exists()).toBe(true);
  });

  it("refetches the task when side toggle changes", async () => {
    (getTask as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce(baseTaskResp("top"))
      .mockResolvedValueOnce(baseTaskResp("bottom"));

    const router = makeRouter();
    await router.push("/projects/pid-1/labeling");
    const wrapper = mount(LabelingView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    await wrapper.find('[data-testid="side-toggle-bottom"]').trigger("click");
    await flushPromises();

    expect(getTask).toHaveBeenCalledTimes(2);
    expect(getTask).toHaveBeenLastCalledWith("pid-1", "bottom");
  });

  it("submits the annotation via the API on LSFEmbed submit emit", async () => {
    (getTask as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      baseTaskResp("top"),
    );
    (submitLabels as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: "label-1",
      project_id: "pid-1",
      side: "top",
      version: 3,
      snapshot_at: "2026-05-23T00:00:00Z",
    });

    const router = makeRouter();
    await router.push("/projects/pid-1/labeling");
    const wrapper = mount(LabelingView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    const stub = wrapper.findComponent({ name: "LSFEmbedStub" });
    stub.vm.$emit("submit", { result: [{ id: "abc" }] });
    await flushPromises();

    expect(submitLabels).toHaveBeenCalledWith("pid-1", "top", {
      result: [{ id: "abc" }],
    });
    expect(wrapper.find('[data-testid="save-indicator"]').text()).toContain("v3");
  });

  it("shows an error envelope when getTask fails with 422", async () => {
    (getTask as unknown as ReturnType<typeof vi.fn>).mockRejectedValue({
      response: { status: 422, data: { message: "golden_top missing" } },
      message: "Request failed with status code 422",
    });

    const router = makeRouter();
    await router.push("/projects/pid-1/labeling");
    const wrapper = mount(LabelingView, {
      global: { plugins: [router] },
    });
    await flushPromises();

    const err = wrapper.find('[data-testid="labeling-error"]');
    expect(err.exists()).toBe(true);
    expect(err.text()).toContain("golden_top missing");
  });
});
