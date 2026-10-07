import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: 'mission-export-map.spec.ts',
  workers: 1,
  retries: 0,
  timeout: 120_000,
  reporter: 'line',
  outputDir: process.env.MISSION_MAP_TEST_OUTPUT ?? 'test-results/mission-map',
});
