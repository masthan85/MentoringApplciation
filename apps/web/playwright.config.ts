import { existsSync } from "node:fs";
import { defineConfig, devices } from "@playwright/test";

// Browsers can be pre-installed (CI image, cloud sandbox). Otherwise Playwright's own are used.
const preinstalled = process.env.PW_CHROMIUM_PATH ?? "/opt/pw-browsers/chromium";
const executablePath = existsSync(preinstalled) ? preinstalled : undefined;

const apiEnv = {
  ENV: "test",
  AUTH_MODE: "dev",
  DEV_AUTH_SECRET: "e2e-secret-e2e-secret-e2e-secret-0123456789",
  LLM_DEFAULT_PROVIDER: "mock",
  JOBS_MODE: "inline",
  DATABASE_URL: "postgresql+asyncpg://mentor_app:mentor_app@localhost:5432/mentor",
  CORS_ORIGINS: '["http://localhost:3100"]',
  RATE_LIMIT_PER_IP: "100000",
  RATE_LIMIT_PER_USER: "100000",
};

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run uvicorn app.main:create_app --factory --port 8100",
      cwd: "../api",
      url: "http://localhost:8100/healthz",
      env: apiEnv,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run build && npm run start -- -p 3100",
      url: "http://localhost:3100/healthz",
      env: { NEXT_PUBLIC_API_URL: "http://localhost:8100" },
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
