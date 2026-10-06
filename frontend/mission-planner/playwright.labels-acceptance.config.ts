import config from './playwright.window-acceptance.config';
import { defineConfig } from '@playwright/test';

// Run the tracked browser fixture against an already-built production image.
export default defineConfig({
  ...config,
  testMatch: [
    'overview-label-callouts.spec.ts',
    'overview-label-occlusion.spec.ts',
    'overview-adsb.spec.ts',
  ],
  outputDir:
    process.env.OVERVIEW_ACCEPTANCE_OUTPUT_DIR ?? 'test-results/label-callouts',
});
