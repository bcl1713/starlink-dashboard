/// <reference types="node" />
import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.WEATHER_ACCEPTANCE_BASE_URL;
let url: URL;
try {
  url = new URL(baseURL ?? '');
  if (
    url.protocol !== 'http:' ||
    !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash
  )
    throw new Error();
} catch {
  throw new Error(
    'WEATHER_ACCEPTANCE_BASE_URL requires a loopback HTTP origin'
  );
}
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'overview-weather-production.spec.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  workers: 1,
  retries: 0,
  timeout: 480_000,
  reporter: 'line',
  outputDir:
    process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/weather-production',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    viewport: { width: 1920, height: 1080 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
