import { defineStore } from "pinia";

import {
  login as apiLogin,
  logout as apiLogout,
  me as apiMe,
  refresh as apiRefresh,
  signup as apiSignup,
  type AuthUser,
  type LoginPayload,
  type SignupPayload,
} from "../api/auth";

const TOKEN_KEY = "ive.access_token";

type State = {
  token: string | null;
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
};

export const useAuthStore = defineStore("auth", {
  state: (): State => ({
    token: typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null,
    user: null,
    loading: false,
    error: null,
  }),
  getters: {
    isAuthenticated: (state) => state.token !== null,
  },
  actions: {
    _persistToken(token: string | null): void {
      this.token = token;
      if (typeof localStorage === "undefined") return;
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    },

    async login(payload: LoginPayload): Promise<void> {
      this.loading = true;
      this.error = null;
      try {
        const result = await apiLogin(payload);
        this._persistToken(result.access_token);
        this.user = result.user;
      } catch (e: unknown) {
        this.error = e instanceof Error ? e.message : "login failed";
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async signup(payload: SignupPayload): Promise<void> {
      this.loading = true;
      this.error = null;
      try {
        const result = await apiSignup(payload);
        this._persistToken(result.access_token);
        this.user = result.user;
      } catch (e: unknown) {
        this.error = e instanceof Error ? e.message : "signup failed";
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async refresh(): Promise<void> {
      const result = await apiRefresh();
      this._persistToken(result.access_token);
      this.user = result.user;
    },

    async loadCurrentUser(): Promise<void> {
      if (!this.token) return;
      try {
        this.user = await apiMe();
      } catch {
        this._persistToken(null);
        this.user = null;
      }
    },

    async logout(): Promise<void> {
      try {
        await apiLogout();
      } catch {
        // ignore; clearing local state is the important part
      }
      this._persistToken(null);
      this.user = null;
    },
  },
});
