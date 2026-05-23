import { describe, expect, it, beforeEach, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";

import EvalView from "../views/EvalView.vue";
import * as evalApi from "../api/eval";

vi.mock("../api/eval");

function buildRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "dashboard", component: { template: "<div />" } },
      {
        path: "/projects/:id/eval/:runId",
        name: "eval",
        component: EvalView,
      },
    ],
  });
  return router;
}

const FULL_EVAL = {
  run_id: "run-xyz",
  metrics: {
    mAP: 0.87,
    per_component_f1: { C4: 0.92, R7: 0.81, U1: 0.66 },
  },
  predictions: [
    {
      designator: "C4",
      bbox: [0.1, 0.2, 0.05, 0.07],
      verdict: "fail",
      is_false_positive: true,
      is_false_negative: false,
      score: 0.91,
    },
    {
      designator: "R7",
      bbox: [0.45, 0.55, 0.04, 0.04],
      verdict: "pass",
      is_false_positive: false,
      is_false_negative: true,
      score: 0.32,
    },
    {
      designator: "U1",
      bbox: [0.6, 0.3, 0.1, 0.12],
      verdict: "fail",
      is_false_positive: true,
      is_false_negative: false,
      score: 0.88,
    },
  ],
  prev_metrics: {
    mAP: 0.81,
    per_component_f1: { C4: 0.88, R7: 0.78, U1: 0.60 },
  },
};

describe("EvalView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
  });

  it("renders metrics, per-component F1 chart, and predictions grid", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue(FULL_EVAL);

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz");
    await router.isReady();

    const wrapper = mount(EvalView, { global: { plugins: [router] } });
    await flushPromises();

    expect(evalApi.getEval).toHaveBeenCalledWith("run-xyz");

    // mAP rendered in header
    expect(wrapper.find('[data-testid="eval-map"]').text()).toContain("0.87");

    // Per-component F1 chart rendered with each designator
    const chart = wrapper.find('[data-testid="metric-chart"]');
    expect(chart.exists()).toBe(true);
    expect(chart.text()).toContain("C4");
    expect(chart.text()).toContain("R7");
    expect(chart.text()).toContain("U1");

    // Predictions grid renders FP + FN
    const grid = wrapper.find('[data-testid="prediction-grid"]');
    expect(grid.exists()).toBe(true);
    expect(grid.html()).toContain("C4");
    expect(grid.html()).toContain("R7");
  });

  it("renders delta indicator vs prev_metrics", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue(FULL_EVAL);

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz");
    await router.isReady();

    const wrapper = mount(EvalView, { global: { plugins: [router] } });
    await flushPromises();

    // delta = 0.87 - 0.81 = +0.06 → up arrow + green text
    const delta = wrapper.find('[data-testid="eval-map-delta"]');
    expect(delta.exists()).toBe(true);
    expect(delta.text()).toContain("0.06");
    expect(delta.classes().join(" ")).toMatch(/success|text-success/);
  });

  it("renders gracefully when prev_metrics is null (first successful run)", async () => {
    vi.mocked(evalApi.getEval).mockResolvedValue({
      ...FULL_EVAL,
      prev_metrics: null,
    });

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-xyz");
    await router.isReady();

    const wrapper = mount(EvalView, { global: { plugins: [router] } });
    await flushPromises();

    // No delta indicator shown when there's no previous run to compare to.
    expect(wrapper.find('[data-testid="eval-map-delta"]').exists()).toBe(false);

    // Empty-state hint instead.
    const noPrev = wrapper.find('[data-testid="eval-no-prev"]');
    expect(noPrev.exists()).toBe(true);
    expect(noPrev.text().toLowerCase()).toMatch(/pertama|sebelumnya/);
  });

  it("renders error message when the backend returns 422 (run not succeeded)", async () => {
    vi.mocked(evalApi.getEval).mockRejectedValue({
      response: {
        status: 422,
        data: {
          message:
            "train_run is in status='running'; eval is only available after the run reaches 'succeeded'",
        },
      },
    });

    const router = buildRouter();
    await router.push("/projects/pid-1/eval/run-running");
    await router.isReady();

    const wrapper = mount(EvalView, { global: { plugins: [router] } });
    await flushPromises();

    const err = wrapper.find('[data-testid="eval-error"]');
    expect(err.exists()).toBe(true);
    expect(err.text().toLowerCase()).toContain("succeeded");
  });
});
