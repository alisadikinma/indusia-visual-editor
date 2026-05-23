import { describe, expect, it, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";

import Gate2View from "../views/Gate2View.vue";
import * as deployApi from "../api/deploy";
import * as evalApi from "../api/eval";

vi.mock("../api/deploy");
vi.mock("../api/eval");

function buildRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "dashboard", component: { template: "<div />" } },
      {
        path: "/projects/:id/eval/:runId/gate2",
        name: "gate2",
        component: Gate2View,
      },
    ],
  });
  return router;
}

const EVAL = {
  run_id: "run-xyz",
  metrics: {
    mAP: 0.87,
    per_component_f1: { C4: 0.92, R7: 0.81 },
  },
  predictions: [],
  prev_metrics: { mAP: 0.81, per_component_f1: { C4: 0.88, R7: 0.78 } },
};

describe("Gate2View", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
  });

  it("renders eval summary + previous deployment + Promote button", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue(EVAL);
    vi.mocked(deployApi.getDeployHistory).mockResolvedValue([
      {
        id: "dep-old",
        project_id: "pid-1",
        train_run_id: "run-prev",
        model_version: "20260101-120000-abc123",
        status: "succeeded",
        edges_notified: null,
        deployed_at: "2026-01-01T12:00:00Z",
        error_text: null,
      },
    ]);

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz/gate2");
    await router.isReady();

    const wrapper = mount(Gate2View, { global: { plugins: [router] } });
    await flushPromises();

    expect(evalApi.getEval).toHaveBeenCalledWith("run-xyz");
    expect(deployApi.getDeployHistory).toHaveBeenCalledWith("pid-1");

    const html = wrapper.html();
    expect(html).toContain("0.87"); // current mAP
    expect(html).toContain("20260101-120000-abc123"); // prev deployment version

    const btn = wrapper.find('[data-testid="promote-button"]');
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("disabled")).toBeFalsy();
  });

  it("opens confirmation modal on Promote click, does not call API until confirmed", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue(EVAL);
    vi.mocked(deployApi.getDeployHistory).mockResolvedValue([]);

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz/gate2");
    await router.isReady();

    const wrapper = mount(Gate2View, { global: { plugins: [router] } });
    await flushPromises();

    expect(wrapper.find('[data-testid="confirm-modal"]').exists()).toBe(false);

    await wrapper.find('[data-testid="promote-button"]').trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="confirm-modal"]').exists()).toBe(true);
    expect(deployApi.promoteToProduction).not.toHaveBeenCalled();
  });

  it("clicking confirm in modal triggers promoteToProduction with project id", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue(EVAL);
    vi.mocked(deployApi.getDeployHistory).mockResolvedValue([]);
    vi.mocked(deployApi.promoteToProduction).mockResolvedValue({
      id: "dep-new",
      project_id: "pid-1",
      train_run_id: "run-xyz",
      model_version: "20260523-080000-xyz",
      status: "succeeded",
      edges_notified: null,
      deployed_at: new Date().toISOString(),
      error_text: null,
    });

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz/gate2");
    await router.isReady();

    const wrapper = mount(Gate2View, { global: { plugins: [router] } });
    await flushPromises();

    await wrapper.find('[data-testid="promote-button"]').trigger("click");
    await flushPromises();
    await wrapper
      .find('[data-testid="confirm-modal-confirm"]')
      .trigger("click");
    await flushPromises();

    expect(deployApi.promoteToProduction).toHaveBeenCalledWith("pid-1");
    // Success badge replaces the modal.
    expect(wrapper.find('[data-testid="promote-success"]').exists()).toBe(true);
  });

  it("clicking cancel in modal closes it without calling API", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue(EVAL);
    vi.mocked(deployApi.getDeployHistory).mockResolvedValue([]);

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz/gate2");
    await router.isReady();

    const wrapper = mount(Gate2View, { global: { plugins: [router] } });
    await flushPromises();

    await wrapper.find('[data-testid="promote-button"]').trigger("click");
    await flushPromises();
    await wrapper
      .find('[data-testid="confirm-modal-cancel"]')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="confirm-modal"]').exists()).toBe(false);
    expect(deployApi.promoteToProduction).not.toHaveBeenCalled();
  });
});
