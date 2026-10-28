import { defineConfig } from '@playwright/test';
if (!process.env.OPERATOR_SYNC_ORIGIN || !process.env.OPERATOR_SYNC_EVIDENCE)
  throw new Error(
    'An owned production origin and evidence directory are required'
  );
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'operator-record-sync.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 480_000,
  expect: { timeout: 5000 },
  reporter: 'list',
  outputDir: `${process.env.OPERATOR_SYNC_EVIDENCE}/playwright`,
  use: {
    baseURL: process.env.OPERATOR_SYNC_ORIGIN,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 15_000,
    launchOptions: {
      executablePath: process.env.OPERATOR_SYNC_CHROMIUM,
      args: [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
      ],
    },
  },
});
