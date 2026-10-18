import { defineConfig } from '@playwright/test';
const origin = new URL(process.env.WEATHER_ACCEPTANCE_BASE_URL ?? '');
if (
  origin.protocol !== 'http:' ||
  origin.hostname !== '127.0.0.1' ||
  !process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR ||
  !process.env.AVIATION_ACCEPTANCE_BROWSER
)
  throw new Error('Owned local display proof and existing browser required');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'operator-display.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 480000,
  expect: { timeout: 30000 },
  reporter: 'list',
  outputDir: `${process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR}/display-browser`,
  use: {
    baseURL: origin.origin,
    viewport: { width: 1920, height: 1080 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: {
      executablePath: process.env.AVIATION_ACCEPTANCE_BROWSER,
      args: [
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--no-sandbox',
        '--disable-dev-shm-usage',
      ],
    },
  },
});
