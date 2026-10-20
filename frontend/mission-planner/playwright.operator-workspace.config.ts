import { defineConfig } from '@playwright/test';

if (!process.env.OPERATOR_ACCEPTANCE_ORIGIN)
  throw new Error('The owned production origin is required');

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: [
    'operator-workspace.spec.ts',
    'operator-layout.spec.ts',
    'operator-workspace-release.spec.ts',
  ],
  workers: 1,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 10_000 },
  reporter: 'list',
  outputDir: `${process.env.OPERATOR_ACCEPTANCE_EVIDENCE}/workspace-playwright`,
  use: {
    baseURL: process.env.OPERATOR_ACCEPTANCE_ORIGIN,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on',
    launchOptions: { args: ['--disable-dev-shm-usage', '--no-sandbox'] },
  },
});
