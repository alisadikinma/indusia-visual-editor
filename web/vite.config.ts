/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import path from "node:path";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: "0.0.0.0",
  },
  test: {
    environment: "happy-dom",
    globals: true,
    include: ["src/**/__tests__/**/*.{spec,test}.{ts,tsx}"],
  },
});
