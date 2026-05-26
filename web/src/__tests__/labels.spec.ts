import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const apiMocks = vi.hoisted(() => ({
  getTask: vi.fn(),
  submitLabels: vi.fn(),
  absoluteImageUrl: (rel: string) => `http://localhost:8002${rel}`,
}));

const prelabelMocks = vi.hoisted(() => ({
  runPreLabel: vi.fn(),
  getPreLabel: vi.fn(),
}));

vi.mock("../api/labels", () => apiMocks);
vi.mock("../api/prelabel", () => prelabelMocks);

import { useLabelsStore } from "../stores/labels";

const taskFor = (side: "top" | "bottom" = "top") => ({
  config: "<View><Image /></View>",
  task: {
    id: 1,
    data: { image: `/api/projects/pid-1/assets/asset-${side}/binary` },
    predictions: [{ id: "pred-old" }],
    annotations: [],
  },
  side,
  designator_count: 5,
});

describe("useLabelsStore.refreshPredictions", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    apiMocks.getTask.mockReset();
    apiMocks.submitLabels.mockReset();
    prelabelMocks.runPreLabel.mockReset();
    prelabelMocks.getPreLabel.mockReset();
  });

  it("re-runs prelabel then refetches task with fresh predictions", async () => {
    apiMocks.getTask.mockResolvedValueOnce(taskFor("top"));
    const store = useLabelsStore();
    await store.fetchTask("pid-1", "top");

    const refreshed = taskFor("top");
    refreshed.task.predictions = [{ id: "pred-new-1" }, { id: "pred-new-2" }];
    apiMocks.getTask.mockResolvedValueOnce(refreshed);
    prelabelMocks.runPreLabel.mockResolvedValueOnce({
      id: "pre-run-2",
      project_id: "pid-1",
      side: "top",
      regions: [],
      created_at: "2026-05-26T00:00:00Z",
    });

    await store.refreshPredictions("pid-1");

    expect(prelabelMocks.runPreLabel).toHaveBeenCalledWith("pid-1", "top");
    expect(apiMocks.getTask).toHaveBeenLastCalledWith("pid-1", "top");
    expect(store.task?.task.predictions).toHaveLength(2);
    expect(store.refreshing).toBe(false);
  });

  it("toggles refreshing flag during the call and clears it on success", async () => {
    apiMocks.getTask.mockResolvedValueOnce(taskFor("top"));
    const store = useLabelsStore();
    await store.fetchTask("pid-1", "top");

    let observed = false;
    prelabelMocks.runPreLabel.mockImplementationOnce(async () => {
      observed = store.refreshing;
      return {
        id: "pre-run-2",
        project_id: "pid-1",
        side: "top",
        regions: [],
        created_at: "2026-05-26T00:00:00Z",
      };
    });
    apiMocks.getTask.mockResolvedValueOnce(taskFor("top"));

    await store.refreshPredictions("pid-1");

    expect(observed).toBe(true);
    expect(store.refreshing).toBe(false);
  });

  it("surfaces backend error envelope and clears refreshing flag", async () => {
    apiMocks.getTask.mockResolvedValueOnce(taskFor("top"));
    const store = useLabelsStore();
    await store.fetchTask("pid-1", "top");

    prelabelMocks.runPreLabel.mockRejectedValueOnce({
      response: { status: 502, data: { message: "Ollama timeout" } },
      message: "Request failed with status code 502",
    });

    await store.refreshPredictions("pid-1");

    expect(store.error).toBe("Ollama timeout");
    expect(store.refreshing).toBe(false);
    expect(apiMocks.getTask).toHaveBeenCalledTimes(1);
  });

  it("uses the currently selected side, not a hardcoded one", async () => {
    apiMocks.getTask.mockResolvedValueOnce(taskFor("bottom"));
    const store = useLabelsStore();
    await store.fetchTask("pid-1", "bottom");

    prelabelMocks.runPreLabel.mockResolvedValueOnce({
      id: "pre-run-3",
      project_id: "pid-1",
      side: "bottom",
      regions: [],
      created_at: "2026-05-26T00:00:00Z",
    });
    apiMocks.getTask.mockResolvedValueOnce(taskFor("bottom"));

    await store.refreshPredictions("pid-1");

    expect(prelabelMocks.runPreLabel).toHaveBeenCalledWith("pid-1", "bottom");
  });
});
