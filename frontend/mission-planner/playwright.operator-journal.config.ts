import { defineConfig } from '@playwright/test';

if (!process.env.OPERATOR_ACCEPTANCE_ORIGIN)
  throw new Error('The owned production origin is required');

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: [
    'operator-journal.spec.ts',
    'operator-shell.spec.ts',
    'operator-displays.spec.ts',
  ],
  workers: 1,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 20_000 },
  reporter: 'list',
  outputDir: `${process.env.OPERATOR_ACCEPTANCE_EVIDENCE}/playwright`,
  use: {
    actionTimeout: 20_000,
    baseURL: process.env.OPERATOR_ACCEPTANCE_ORIGIN,
    headless: true,
    launchOptions: { args: ['--disable-dev-shm-usage', '--no-sandbox'] },
  },
});
