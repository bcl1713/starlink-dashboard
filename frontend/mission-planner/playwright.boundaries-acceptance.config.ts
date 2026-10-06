import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'overview-boundaries-production.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: 'line',
  outputDir:
    process.env.BOUNDARY_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/boundaries-production',
  use: {
    baseURL: 'http://127.0.0.1:15282',
    trace: 'retain-on-failure',
    viewport: { width: 1920, height: 1080 },
    launchOptions: { args: ['--use-gl=angle', '--use-angle=swiftshader'] },
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1920, height: 1080 },
      },
    },
  ],
});
