/// <reference types="vite/client" />
import axios, { type AxiosInstance, type AxiosRequestConfig } from "axios";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const TOKEN_KEY = "ive.access_token";

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

export type ApiEnvelope<T> = {
  status: boolean;
  message: string;
  data: T;
};

// Phase 13.5 — attach the bearer access token from localStorage to every
// outbound request. We avoid importing the Pinia store here so the api
// layer stays consumable from non-Vue contexts (tests, workers).
api.interceptors.request.use((config) => {
  const token = typeof localStorage !== "undefined" ? localStorage.getItem(TOKEN_KEY) : null;
  if (token) {
    config.headers.set?.("Authorization", `Bearer ${token}`);
    // Older versions of axios use a plain object — set both ways defensively.
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

// Phase 13.5 — on 401, try the refresh endpoint exactly once and replay
// the original request. If refresh also 401s, give up — the auth store /
// router guard will redirect to /login.
let refreshing: Promise<string | null> | null = null;

async function attemptRefresh(): Promise<string | null> {
  try {
    const response = await axios.post<ApiEnvelope<{ access_token: string }>>(
      `${baseURL}/api/auth/refresh`,
      {},
      { withCredentials: true },
    );
    const token = response.data.data.access_token;
    if (typeof localStorage !== "undefined") localStorage.setItem(TOKEN_KEY, token);
    return token;
  } catch {
    if (typeof localStorage !== "undefined") localStorage.removeItem(TOKEN_KEY);
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined;
    const status = error.response?.status;
    if (status !== 401 || !original || original._retry) {
      return Promise.reject(error);
    }
    // Don't loop on the refresh call itself.
    if (typeof original.url === "string" && original.url.includes("/api/auth/")) {
      return Promise.reject(error);
    }
    original._retry = true;
    refreshing ??= attemptRefresh();
    const token = await refreshing;
    refreshing = null;
    if (!token) return Promise.reject(error);
    original.headers ??= {};
    (original.headers as Record<string, string>).Authorization = `Bearer ${token}`;
    return api.request(original);
  },
);
