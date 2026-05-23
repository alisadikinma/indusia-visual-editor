import { api, type ApiEnvelope } from "./client";

export type AuthUser = {
  id: string;
  email: string;
  role: "admin" | "engineer" | "viewer";
  organization_id: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  user: AuthUser;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type SignupPayload = {
  email: string;
  password: string;
  organization_slug?: string;
};

export async function signup(payload: SignupPayload): Promise<TokenResponse> {
  const response = await api.post<ApiEnvelope<TokenResponse>>(
    "/api/auth/signup",
    payload,
    { withCredentials: true },
  );
  return response.data.data;
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const response = await api.post<ApiEnvelope<TokenResponse>>(
    "/api/auth/login",
    payload,
    { withCredentials: true },
  );
  return response.data.data;
}

export async function refresh(): Promise<TokenResponse> {
  const response = await api.post<ApiEnvelope<TokenResponse>>(
    "/api/auth/refresh",
    {},
    { withCredentials: true },
  );
  return response.data.data;
}

export async function logout(): Promise<void> {
  await api.post("/api/auth/logout", {}, { withCredentials: true });
}

export async function me(): Promise<AuthUser> {
  const response = await api.get<ApiEnvelope<AuthUser>>("/api/auth/me");
  return response.data.data;
}
