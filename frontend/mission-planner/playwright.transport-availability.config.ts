import { defineConfig } from '@playwright/test';
if (!process.env.TRANSPORT_ACCEPTANCE_ORIGIN)
  throw new Error('An owned exact-SHA production origin is required');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'transport-availability.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 600_000,
  expect: { timeout: 15_000 },
  reporter: 'list',
  outputDir: `${process.env.TRANSPORT_ACCEPTANCE_EVIDENCE}/playwright`,
  use: {
    baseURL: process.env.TRANSPORT_ACCEPTANCE_ORIGIN,
    viewport: { width: 1920, height: 1080 },
    headless: true,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    screenshot: 'only-on-failure',
    trace: 'on',
    launchOptions: { args: ['--disable-dev-shm-usage', '--no-sandbox'] },
  },
});
