import windowAcceptance from './playwright.window-acceptance.config';
import { defineConfig } from '@playwright/test';

export default defineConfig({
  ...windowAcceptance,
  testMatch: [
    'overview-ui-cleanup-production.spec.ts',
    'overview-window-compact.spec.ts',
  ],
  timeout: 240_000,
  use: {
    ...windowAcceptance.use,
    launchOptions: {
      executablePath: process.env.OVERVIEW_ACCEPTANCE_BROWSER,
      args: ['--enable-unsafe-swiftshader'],
    },
  },
});
