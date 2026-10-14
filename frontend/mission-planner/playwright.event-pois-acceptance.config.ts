import { defineConfig } from '@playwright/test';
import acceptance from './playwright.window-acceptance.config';

export default defineConfig(acceptance, {
  testMatch: 'event-pois-production.spec.ts',
  outputDir:
    process.env.OVERVIEW_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/event-pois-production',
});
