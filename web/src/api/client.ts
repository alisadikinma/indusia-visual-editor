/// <reference types="vite/client" />
import axios, { type AxiosInstance } from "axios";

const baseURL = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

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
