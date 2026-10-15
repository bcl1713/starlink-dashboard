import { defineConfig } from '@playwright/test';
import configuration from './playwright.window-acceptance.config';

export default defineConfig({
  ...configuration,
  testMatch: 'manual-x-selection-production.spec.ts',
  outputDir:
    process.env.OVERVIEW_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/manual-x-production',
});
