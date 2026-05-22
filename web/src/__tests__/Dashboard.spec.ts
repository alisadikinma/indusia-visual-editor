import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory, type Router } from "vue-router";

import Dashboard from "../views/Dashboard.vue";
import { routes } from "../router";
import { useProjectsStore } from "../stores/projects";
import type { Project } from "../api/projects";

const sampleProjects: Project[] = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    name: "NV80-017542-0501",
    slug: "nv80-017542-0501",
    status: "deployed",
    created_at: "2026-05-10T10:00:00Z",
    updated_at: "2026-05-22T08:00:00Z",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    name: "Board A",
    slug: "board-a",
    status: "drafting",
    created_at: "2026-05-22T07:55:00Z",
    updated_at: "2026-05-22T07:55:00Z",
  },
];

function buildRouter(): Router {
  return createRouter({ history: createMemoryHistory(), routes });
}

describe("Dashboard", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("renders the New Project button and the empty-state copy when no projects exist", async () => {
    const store = useProjectsStore();
    store.items = [];
    store.fetch = vi.fn(async () => {});
    const router = buildRouter();
    const wrapper = mount(Dashboard, { global: { plugins: [router] } });
    await flushPromises();

    expect(wrapper.text()).toContain("Belum ada project");
    expect(wrapper.find('[data-testid="new-project-button"]').exists()).toBe(true);
  });

  it("renders one row per project with name, slug, and a status badge", async () => {
    const store = useProjectsStore();
    store.items = sampleProjects;
    store.fetch = vi.fn(async () => {});
    const router = buildRouter();
    const wrapper = mount(Dashboard, { global: { plugins: [router] } });
    await flushPromises();

    const rows = wrapper.findAll('[data-testid="project-row"]');
    expect(rows).toHaveLength(2);

    expect(rows[0].text()).toContain("NV80-017542-0501");
    expect(rows[0].text()).toContain("nv80-017542-0501");
    expect(rows[0].find('[data-testid="status-badge"]').text()).toBe("Deployed");

    expect(rows[1].find('[data-testid="status-badge"]').text()).toBe("Drafting");
  });

  it("calls store.fetch on mount", async () => {
    const store = useProjectsStore();
    store.items = [];
    const fetchSpy = vi.fn(async () => {});
    store.fetch = fetchSpy;
    const router = buildRouter();
    mount(Dashboard, { global: { plugins: [router] } });
    await flushPromises();
    expect(fetchSpy).toHaveBeenCalledOnce();
  });
});
