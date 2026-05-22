import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createMemoryHistory } from "vue-router";

import App from "../App.vue";
import { routes } from "../router";

describe("App", () => {
  it("mounts the router view at /", async () => {
    setActivePinia(createPinia());

    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    });

    await router.push("/");
    await router.isReady();

    const wrapper = mount(App, { global: { plugins: [router] } });

    // Dashboard route is active — heading "Projects" must render.
    expect(wrapper.find("h1").text()).toBe("Projects");
  });
});
