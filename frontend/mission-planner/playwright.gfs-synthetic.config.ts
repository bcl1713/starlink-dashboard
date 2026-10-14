import { defineConfig } from '@playwright/test';
const baseURL = process.env.WEATHER_ACCEPTANCE_BASE_URL;
const origin = new URL(baseURL ?? '');
if (
  origin.protocol !== 'http:' ||
  !['localhost', '127.0.0.1'].includes(origin.hostname) ||
  origin.pathname !== '/' ||
  origin.username ||
  origin.password ||
  origin.search ||
  origin.hash
)
  throw Error('Synthetic check requires loopback production origin');
if (!process.env.AVIATION_ACCEPTANCE_BROWSER)
  throw Error('Provisioned browser required');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'gfs-wind-synthetic.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 300000,
  reporter: 'line',
  outputDir:
    process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/gfs-wind-synthetic',
  use: {
    baseURL,
    viewport: { width: 1920, height: 1080 },
    trace: 'retain-on-failure',
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
