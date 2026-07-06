import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  use: {
    baseURL: process.env.KINDRED_E2E_URL ?? "http://127.0.0.1:8000",
    trace: "retain-on-failure",
  },
  reporter: "line",
});

