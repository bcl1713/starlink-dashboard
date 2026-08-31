import { defineConfig, devices } from '@playwright/test';

const port = process.env.PLAYWRIGHT_PORT || '5173';
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
const harPath = process.env.OVERVIEW_HAR_PATH;

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 90_000,
  workers: undefined,
  reporter: 'line',
  use: {
    baseURL: `http://localhost:${port}`,
    trace: process.env.OVERVIEW_TRACE ? 'on' : 'off',
    video: process.env.OVERVIEW_VIDEO ? 'on' : 'off',
    contextOptions: harPath
      ? { recordHar: { path: harPath, mode: 'full' } }
      : undefined,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        headless: process.env.PLAYWRIGHT_HEADED ? false : undefined,
        launchOptions: executablePath ? { executablePath } : undefined,
      },
    },
  ],
  webServer: {
    command: `npm run preview -- --port ${port}`,
    url: `http://localhost:${port}`,
    reuseExistingServer: false, // Always start a new server for local runs
  },
});
