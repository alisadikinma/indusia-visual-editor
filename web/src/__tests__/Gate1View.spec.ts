import { describe, expect, it, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";

import Gate1View from "../views/Gate1View.vue";
import * as datasetApi from "../api/dataset_stats";
import * as trainingApi from "../api/training";

vi.mock("../api/dataset_stats");
vi.mock("../api/training");

function buildRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "dashboard", component: { template: "<div />" } },
      { path: "/projects/:id/gate1", name: "gate1", component: Gate1View },
      {
        path: "/projects/:id/training/:runId",
        name: "training-progress",
        component: { template: "<div />" },
      },
    ],
  });
  return router;
}

const SUGGESTION = {
  project_id: "pid-1",
  side: "top" as const,
  stats: {
    project_id: "pid-1",
    side: "top" as const,
    label_version: 1,
    total: 4,
    inspected: 3,
    skipped: 1,
    per_criterion: {
      missing_component: 2,
      orientation: 1,
      polarity_flip: 0,
      connector_pin_bending: 0,
      missing_pin_connector: 0,
      lifted_pin: 0,
      wrong_value: 0,
      misalignment: 0,
      solder_short: 0,
    },
    mi_count: 2,
    smt_count: 1,
    designators: [
      {
        designator: "R1",
        inspect_scope: "inspected" as const,
        scope_mode: "per_component" as const,
        defect_criteria: ["missing_component"],
        mi_likely: true,
      },
    ],
  },
  hyperparameters: {
    epochs: 40,
    batch_size: 16,
    augmentation_intensity: "medium" as const,
    notes: "Distribusi seimbang; aug medium cukup.",
  },
};

describe("Gate1View", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
  });

  it("renders stats grid and Gemma hyperparam suggestion on mount", async () => {
    vi.mocked(trainingApi.suggestHyperparams).mockResolvedValue(SUGGESTION);

    const router = buildRouter();
    await router.push("/projects/pid-1/gate1");
    await router.isReady();

    const wrapper = mount(Gate1View, { global: { plugins: [router] } });
    await flushPromises();

    expect(trainingApi.suggestHyperparams).toHaveBeenCalledWith("pid-1", "top");

    const html = wrapper.html();
    expect(html).toContain("3"); // inspected
    expect(html).toContain("1"); // skipped
    expect(html).toContain("missing_component");
    expect(html).toContain("40"); // epochs
    expect(html).toContain("medium");

    const btn = wrapper.find('[data-testid="start-training-button"]');
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("disabled")).toBeFalsy();
    expect(btn.text()).toContain("Mulai");
  });

  it("disables the Mulai Training button when no labels exist (404)", async () => {
    vi.mocked(trainingApi.suggestHyperparams).mockRejectedValue({
      response: { status: 404, data: { message: "no label yet for side=top" } },
    });

    const router = buildRouter();
    await router.push("/projects/pid-1/gate1");
    await router.isReady();

    const wrapper = mount(Gate1View, { global: { plugins: [router] } });
    await flushPromises();

    const btn = wrapper.find('[data-testid="start-training-button"]');
    expect(btn.exists()).toBe(true);
    expect(btn.attributes("disabled")).toBeDefined();

    const empty = wrapper.find('[data-testid="gate1-empty"]');
    expect(empty.exists()).toBe(true);
    expect(empty.text().toLowerCase()).toContain("label");
  });

  it("clicking Mulai Training calls startTraining and navigates to progress view", async () => {
    vi.mocked(trainingApi.suggestHyperparams).mockResolvedValue(SUGGESTION);
    vi.mocked(trainingApi.startTraining).mockResolvedValue({
      id: "run-xyz",
      project_id: "pid-1",
      adapt_run_id: "adapt-1",
      service_job_id: "job-1",
      status: "pending",
      metrics_json: null,
      started_at: new Date().toISOString(),
      ended_at: null,
      error_text: null,
    });

    const router = buildRouter();
    await router.push("/projects/pid-1/gate1");
    await router.isReady();
    const pushSpy = vi.spyOn(router, "push");

    const wrapper = mount(Gate1View, { global: { plugins: [router] } });
    await flushPromises();

    await wrapper.find('[data-testid="start-training-button"]').trigger("click");
    await flushPromises();

    expect(trainingApi.startTraining).toHaveBeenCalledWith("pid-1");
    expect(pushSpy).toHaveBeenCalledWith({
      name: "training-progress",
      params: { id: "pid-1", runId: "run-xyz" },
    });
  });
});
