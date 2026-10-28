import { defineConfig } from '@playwright/test';
if (
  !process.env.OVERVIEW_ADVISORIES_ORIGIN ||
  !process.env.OVERVIEW_ADVISORIES_EVIDENCE
)
  throw new Error(
    'An owned production origin and evidence directory are required'
  );
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'overview-advisories.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 420_000,
  expect: { timeout: 30_000 },
  reporter: 'list',
  outputDir: `${process.env.OVERVIEW_ADVISORIES_EVIDENCE}/playwright`,
  use: {
    baseURL: process.env.OVERVIEW_ADVISORIES_ORIGIN,
    headless: true,
    actionTimeout: 20_000,
    launchOptions: {
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
