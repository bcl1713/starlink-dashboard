import { defineConfig } from '@playwright/test';

if (!process.env.OPERATOR_ACCEPTANCE_ORIGIN)
  throw new Error('The owned production origin is required');

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'mission-timeline.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 180000,
  expect: { timeout: 20000 },
  reporter: 'list',
  outputDir: `${process.env.OPERATOR_ACCEPTANCE_EVIDENCE}/mission-timeline-playwright`,
  use: {
    baseURL: process.env.OPERATOR_ACCEPTANCE_ORIGIN,
    headless: true,
    actionTimeout: 20000,
    launchOptions: { args: ['--disable-dev-shm-usage', '--no-sandbox'] },
  },
});
