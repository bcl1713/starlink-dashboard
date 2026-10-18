import { defineConfig } from '@playwright/test';
if (
  !process.env.OPERATOR_TRAINING_ORIGIN ||
  !process.env.OPERATOR_TRAINING_PROOF_ROOT
)
  throw new Error('Owned disposable training origin/root required');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'operator-training-fixture.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 240_000,
  expect: { timeout: 15_000 },
  reporter: 'list',
  outputDir: `${process.env.OPERATOR_TRAINING_PROOF_ROOT}/browser`,
  use: {
    baseURL: process.env.OPERATOR_TRAINING_ORIGIN,
    headless: true,
    actionTimeout: 15_000,
    launchOptions: { args: ['--disable-dev-shm-usage', '--no-sandbox'] },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
