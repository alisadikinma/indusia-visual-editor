import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import App from "../App.vue";
import { routes } from "../router";

describe("App", () => {
  it("renders the active route view", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    });

    await router.push("/");
    await router.isReady();

    const wrapper = mount(App, {
      global: {
        plugins: [router],
      },
    });

    expect(wrapper.html()).toContain("Visual Editor");
  });
});
