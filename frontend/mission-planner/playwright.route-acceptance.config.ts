import { defineConfig } from '@playwright/test';
import acceptance from './playwright.window-acceptance.config';

/** Reuse the guarded loopback origin and exact-candidate acceptance runner. */
export default defineConfig(acceptance, {
  testMatch: 'overview-fullscreen-route.spec.ts',
  grep: /synthetic dateline route/,
  outputDir:
    process.env.OVERVIEW_ACCEPTANCE_OUTPUT_DIR ??
    'test-results/route-production',
});
