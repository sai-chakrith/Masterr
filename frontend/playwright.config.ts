import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
const root = path.resolve(__dirname, "..");
const python = process.env.MASTRR_PYTHON ?? path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3765", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium" } },
  ],
  webServer: [
    { command: `"${python}" -m tests.e2e_server`, cwd: root, url: "http://127.0.0.1:8765/ready", timeout: 120_000, reuseExistingServer: false,
      env: { MASTRR_E2E: "1", LOCAL_DEVELOPMENT: "1", MASTRR_ENV: "development", LOCAL_API_TOKEN: "e2e-only-token-not-a-real-secret-123456", MASTRR_ADMIN_SUBJECTS: "local-developer", GROQ_API_KEY: "", MASTRR_API_REQUESTS_PER_MINUTE: "2000" } },
    { command: "node node_modules/next/dist/bin/next start --port 3765 --hostname 127.0.0.1", url: "http://127.0.0.1:3765/login", timeout: 120_000, reuseExistingServer: false },
  ],
});
