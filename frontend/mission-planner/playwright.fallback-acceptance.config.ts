import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.FALLBACK_ACCEPTANCE_BASE_URL;
const url = new URL(baseURL ?? '');
if (
  url.protocol !== 'http:' ||
  !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
  url.username ||
  url.password ||
  url.pathname !== '/' ||
  url.search ||
  url.hash
) {
  throw new Error(
    'FALLBACK_ACCEPTANCE_BASE_URL requires a loopback HTTP origin'
  );
}

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'overview-fallback-production.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: 'line',
  outputDir:
    process.env.FALLBACK_ACCEPTANCE_OUTPUT_DIR ?? 'test-results/fallback',
  use: {
    baseURL,
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
