import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'pop-transitions.spec.ts',
  timeout: 180_000,
  workers: 1,
  retries: 0,
  reporter: 'line',
  outputDir: process.env.POP_EVIDENCE_ROOT + '/playwright',
  use: { baseURL: process.env.POP_ORIGIN, trace: 'retain-on-failure' },
});
