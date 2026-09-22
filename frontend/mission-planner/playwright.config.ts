/// <reference types="node" />
import { defineConfig, devices } from '@playwright/test';

const port = process.env.PLAYWRIGHT_PORT || '5173';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: undefined,
  reporter: 'line',
  // Cold WebGL startup can exceed Playwright's 30s default before the first page
  // is ready; keep one bounded suite-wide budget rather than retrying failures.
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${port}`,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `npm run build && npm run preview -- --port ${port}`,
    url: `http://localhost:${port}`,
    timeout: 120_000,
    reuseExistingServer: false, // Always start a new server for local runs
  },
});
