import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 300_000,
  expect: {
    timeout: 20_000
  },
  outputDir: "../../artifacts/workbench-alpha/playwright-output",
  reporter: [
    ["list"],
    ["json", { outputFile: "../../artifacts/workbench-alpha/playwright-report/results.json" }],
    ["html", { outputFolder: "../../artifacts/workbench-alpha/playwright-report", open: "never" }]
  ],
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "on"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: {
    command:
      "cd ../.. && PYTHONPATH=src .venv/bin/python -m tqe.workshop.app_service --host 127.0.0.1 --port 8765 --output-root artifacts/workbench-alpha/e2e-workshop",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  }
});
