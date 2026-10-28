import { defineConfig } from '@playwright/test';
if (
  !process.env.OPERATOR_COHERENT_ORIGIN ||
  !process.env.OPERATOR_COHERENT_EVIDENCE
)
  throw new Error(
    'An Owned Production Origin And Evidence Directory Are Required'
  );
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'operator-coherent.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 480_000,
  expect: { timeout: 30_000 },
  reporter: 'list',
  outputDir: `${process.env.OPERATOR_COHERENT_EVIDENCE}/playwright`,
  use: {
    baseURL: process.env.OPERATOR_COHERENT_ORIGIN,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 20_000,
    launchOptions: {
      executablePath: process.env.OPERATOR_COHERENT_CHROMIUM,
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
