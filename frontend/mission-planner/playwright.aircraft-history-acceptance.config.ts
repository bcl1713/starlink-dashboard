import windowAcceptance from './playwright.window-acceptance.config';
import { defineConfig } from '@playwright/test';

export default defineConfig({
  ...windowAcceptance,
  testMatch: 'overview-aircraft-history-production.spec.ts',
  outputDir:
    process.env.OVERVIEW_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/aircraft-history-production',
});
