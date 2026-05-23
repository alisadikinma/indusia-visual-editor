import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

const apiMocks = vi.hoisted(() => ({
  login: vi.fn(),
  signup: vi.fn(),
  refresh: vi.fn(),
  logout: vi.fn(),
  me: vi.fn(),
}));

vi.mock("../api/auth", () => apiMocks);

import { useAuthStore } from "../stores/auth";

describe("useAuthStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    apiMocks.login.mockReset();
    apiMocks.signup.mockReset();
    apiMocks.refresh.mockReset();
    apiMocks.logout.mockReset();
    apiMocks.me.mockReset();
  });

  it("persists access token on successful login", async () => {
    apiMocks.login.mockResolvedValue({
      access_token: "jwt-abc",
      token_type: "Bearer",
      expires_in: 3600,
      user: {
        id: "u1",
        email: "ali@example.com",
        role: "engineer",
        organization_id: "o1",
      },
    });

    const auth = useAuthStore();
    expect(auth.isAuthenticated).toBe(false);

    await auth.login({ email: "ali@example.com", password: "secret-2026" });

    expect(auth.isAuthenticated).toBe(true);
    expect(auth.token).toBe("jwt-abc");
    expect(localStorage.getItem("ive.access_token")).toBe("jwt-abc");
    expect(auth.user?.email).toBe("ali@example.com");
  });

  it("clears token + user on logout", async () => {
    localStorage.setItem("ive.access_token", "stale-jwt");
    apiMocks.logout.mockResolvedValue(undefined);

    const auth = useAuthStore();
    auth.user = {
      id: "u1",
      email: "ali@example.com",
      role: "engineer",
      organization_id: "o1",
    };

    await auth.logout();

    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(localStorage.getItem("ive.access_token")).toBeNull();
  });

  it("captures error on bad login and re-throws", async () => {
    apiMocks.login.mockRejectedValue(new Error("Request failed with status code 401"));

    const auth = useAuthStore();
    await expect(
      auth.login({ email: "x@y.com", password: "no" }),
    ).rejects.toThrow(/401/);
    expect(auth.token).toBeNull();
    expect(auth.error).toContain("401");
  });

  it("signup persists token on success", async () => {
    apiMocks.signup.mockResolvedValue({
      access_token: "jwt-new",
      token_type: "Bearer",
      expires_in: 3600,
      user: {
        id: "u2",
        email: "new@example.com",
        role: "engineer",
        organization_id: "o1",
      },
    });

    const auth = useAuthStore();
    await auth.signup({ email: "new@example.com", password: "secret-2026" });

    expect(auth.token).toBe("jwt-new");
    expect(auth.user?.email).toBe("new@example.com");
  });
});
