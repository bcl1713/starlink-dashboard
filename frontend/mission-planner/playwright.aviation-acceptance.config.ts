import { defineConfig } from '@playwright/test';

const baseURL = process.env.WEATHER_ACCEPTANCE_BASE_URL;
const origin = new URL(baseURL ?? '');
if (
  origin.protocol !== 'http:' ||
  !['127.0.0.1', 'localhost'].includes(origin.hostname) ||
  origin.pathname !== '/' ||
  origin.username ||
  origin.password ||
  origin.search ||
  origin.hash
)
  throw new Error('Aviation acceptance requires a loopback HTTP origin');
const executablePath = process.env.AVIATION_ACCEPTANCE_BROWSER;
if (!executablePath)
  throw new Error('A provisioned browser executable is required');
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: [
    'aviation-weather-production.spec.ts',
    'gfs-weather-production.spec.ts',
  ],
  workers: 1,
  retries: 0,
  timeout: 180000,
  reporter: 'line',
  outputDir: `${process.env.WEATHER_ACCEPTANCE_OUTPUT_DIR ?? 'test-results/aviation-weather'}/playwright`,
  use: {
    baseURL,
    viewport: { width: 1920, height: 1080 },
    trace: 'retain-on-failure',
    launchOptions: {
      executablePath,
      args: [
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--no-sandbox',
        '--disable-dev-shm-usage',
      ],
    },
  },
});
