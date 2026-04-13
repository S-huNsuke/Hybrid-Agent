import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const baseURL = process.env.E2E_BASE_URL || "http://127.0.0.1:3000";
const apiBaseURL = process.env.E2E_API_BASE_URL || "http://127.0.0.1:18000";
const apiHealthURL = process.env.E2E_API_HEALTH_URL || `${apiBaseURL}/health`;
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const frontendRoot = path.resolve(repoRoot, "frontend");
const viteBin = path.resolve(frontendRoot, "node_modules", ".bin", "vite");
const e2eDatabasePath =
  process.env.E2E_DATABASE_PATH
  || path.resolve(repoRoot, ".e2e", "e2e.sqlite3");
const e2eChromaPath =
  process.env.E2E_CHROMA_DB_DIR
  || path.resolve(repoRoot, ".e2e", "chroma_db");

export default defineConfig({
  testDir: ".",
  globalSetup: "./global-setup.mjs",
  timeout: 180000,
  forbidOnly: Boolean(process.env.CI),
  workers: process.env.CI ? 1 : undefined,
  expect: {
    timeout: 25000,
  },
  outputDir: "./artifacts/test-results",
  use: {
    baseURL,
    viewport: { width: 1280, height: 720 },
    actionTimeout: 20000,
    navigationTimeout: 30000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  retries: process.env.CI ? 2 : 0,
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "./artifacts/html-report" }],
  ],
  webServer: [
    {
      command: `/bin/zsh -lc 'mkdir -p "${path.dirname(e2eDatabasePath)}" && rm -f "${e2eDatabasePath}" && rm -rf "${e2eChromaPath}" && UV_CACHE_DIR="${process.env.UV_CACHE_DIR || "/tmp/uv-cache"}" PYTHONPATH="${path.resolve(repoRoot, "src")}" DATABASE_URL="sqlite:///${e2eDatabasePath}" CHROMA_DB_DIR="${e2eChromaPath}" JWT_SECRET_KEY="e2e-jwt-secret-key" PROVIDER_SECRET_KEY="e2e-provider-secret-key" uv run uvicorn hybrid_agent.api.main:app --host 127.0.0.1 --port 18000'`,
      url: apiHealthURL,
      cwd: repoRoot,
      timeout: 120000,
      reuseExistingServer: false,
    },
    {
      command: `${viteBin} --host 127.0.0.1 --port 3000`,
      url: baseURL,
      cwd: frontendRoot,
      env: {
        ...process.env,
        VITE_API_PROXY_TARGET: apiBaseURL,
      },
      timeout: 120000,
      reuseExistingServer: false,
    },
  ],
});
