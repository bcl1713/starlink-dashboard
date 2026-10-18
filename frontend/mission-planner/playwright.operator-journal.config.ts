import { defineConfig } from '@playwright/test';

if (!process.env.OPERATOR_ACCEPTANCE_ORIGIN)
  throw new Error('The owned production origin is required');

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: [
    'operator-journal.spec.ts',
    'operator-shell.spec.ts',
    'operator-displays.spec.ts',
    'operator-communications.spec.ts',
    'operator-conferences.spec.ts',
    'operator-issues.spec.ts',
    ...(process.env.OPERATOR_MODEL_ALERTS_ACCEPTANCE === 'true'
      ? ['operator-model-alerts.spec.ts']
      : []),
    ...(process.env.OPERATOR_EVENTS_ACCEPTANCE === 'true' ||
    process.env.OPERATOR_MODEL_ALERTS_ACCEPTANCE === 'true'
      ? ['operator-events.spec.ts']
      : []),
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
