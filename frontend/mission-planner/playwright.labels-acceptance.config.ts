import config from './playwright.window-acceptance.config';
import { defineConfig } from '@playwright/test';

// Run the tracked browser fixture against an already-built production image.
export default defineConfig({
  ...config,
  // Production globe texture decoding can exceed the default five seconds
  // on the cloud software renderer. Assertions remain bounded and unchanged.
  expect: { timeout: 30_000 },
  use: { ...config.use, actionTimeout: 15_000 },
  testMatch: [
    'overview-label-callouts.spec.ts',
    'overview-label-occlusion.spec.ts',
    'overview-adsb.spec.ts',
  ],
  outputDir:
    process.env.OVERVIEW_ACCEPTANCE_OUTPUT_DIR ?? 'test-results/label-callouts',
});
