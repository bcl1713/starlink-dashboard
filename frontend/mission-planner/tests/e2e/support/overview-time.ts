import type { Page } from '@playwright/test';

export async function installFixedBrowserTime(page: Page, nowIso: string) {
  await page.clock.install({ time: nowIso });
  await page.clock.resume();
}
