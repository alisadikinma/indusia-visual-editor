import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

const apiMocks = vi.hoisted(() => ({
  login: vi.fn(),
  signup: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  me: vi.fn(),
}));

vi.mock("../api/auth", () => apiMocks);

import LoginView from "../views/LoginView.vue";
import { useAuthStore } from "../stores/auth";

function buildRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", component: { template: "<div>home</div>" } },
      { path: "/login", component: LoginView },
      { path: "/signup", component: { template: "<div>signup</div>" } },
    ],
  });
}

describe("LoginView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    apiMocks.login.mockReset();
  });

  it("renders the Bahasa Indonesia heading + submit button", async () => {
    const router = buildRouter();
    await router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, {
      global: { plugins: [router] },
    });

    expect(wrapper.text()).toContain("Masuk ke Indusia Visual Editor");
    expect(wrapper.get('[data-testid="login-submit"]').text()).toContain("Masuk");
  });

  it("calls auth.login on submit and navigates home on success", async () => {
    apiMocks.login.mockResolvedValue({
      access_token: "jwt-abc",
      token_type: "Bearer",
      expires_in: 3600,
      user: {
        id: "u1",
        email: "ali@indusia.dev",
        role: "engineer",
        organization_id: "o1",
      },
    });

    const router = buildRouter();
    await router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, {
      global: { plugins: [router] },
    });

    await wrapper.get('[data-testid="login-email"]').setValue("ali@indusia.dev");
    await wrapper.get('[data-testid="login-password"]').setValue("indusia-2026");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();

    expect(apiMocks.login).toHaveBeenCalledWith({
      email: "ali@indusia.dev",
      password: "indusia-2026",
    });
    const auth = useAuthStore();
    expect(auth.isAuthenticated).toBe(true);
    expect(router.currentRoute.value.path).toBe("/");
  });

  it("surfaces an error envelope from the backend", async () => {
    const err = Object.assign(new Error("401"), {
      response: { data: { status: false, message: "invalid credentials", data: null } },
    });
    apiMocks.login.mockRejectedValue(err);

    const router = buildRouter();
    await router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, {
      global: { plugins: [router] },
    });

    await wrapper.get('[data-testid="login-email"]').setValue("ali@indusia.dev");
    await wrapper.get('[data-testid="login-password"]').setValue("wrong");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.get('[data-testid="login-error"]').text()).toBe(
      "invalid credentials",
    );
  });

  it("disables submit while the request is in flight", async () => {
    let resolve: ((value: unknown) => void) | undefined;
    apiMocks.login.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );

    const router = buildRouter();
    await router.push("/login");
    await router.isReady();

    const wrapper = mount(LoginView, {
      global: { plugins: [router] },
    });
    await wrapper.get('[data-testid="login-email"]').setValue("a@b.dev");
    await wrapper.get('[data-testid="login-password"]').setValue("abcdefgh");
    wrapper.get("form").trigger("submit.prevent");
    await flushPromises();

    expect(
      wrapper.get('[data-testid="login-submit"]').attributes("disabled"),
    ).toBeDefined();

    resolve?.({
      access_token: "tk",
      token_type: "Bearer",
      expires_in: 1,
      user: { id: "u", email: "a@b.dev", role: "engineer", organization_id: "o" },
    });
    await flushPromises();
  });
});
