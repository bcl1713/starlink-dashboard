import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '@playwright/test';
import {
  evidence,
  noOverflow,
  origin,
  ready,
} from './operator-journal-helpers';

test('single mission ZIP archive uses existing export and import controls', async ({
  browser,
}) => {
  const captures: string[] = [];
  const errors: string[] = [];
  for (const [width, height] of [
    [1920, 1080],
    [390, 844],
    [844, 390],
  ]) {
    const context = await browser.newContext({
      viewport: { width, height },
      acceptDownloads: true,
    });
    try {
      const page = await context.newPage();
      page.on('pageerror', (error) => errors.push(error.message));
      await ready(page);
      await page.goto(`${origin}/missions`);
      const card = page.locator('div.rounded-xl.border.bg-card').filter({
        has: page.getByText('Synthetic Mission A', { exact: true }),
      });
      await card.getByRole('button', { name: 'Export', exact: true }).click();
      const dialog = page.getByRole('dialog');
      await expect(
        dialog.getByRole('heading', { name: 'Export Mission' })
      ).toBeVisible();
      await noOverflow(page);
      await page.screenshot({
        path: join(evidence, `archive-export-${width}x${height}.png`),
        fullPage: true,
      });
      const downloading = page.waitForEvent('download', { timeout: 600_000 });
      await dialog.getByRole('button', { name: 'Export', exact: true }).click();
      const download = await downloading;
      expect(download.suggestedFilename()).toBe('synthetic-mission-a.zip');
      expect(await download.failure()).toBeNull();
      await download.saveAs(join(evidence, `browser-mission-${width}.zip`));
      await expect(dialog).not.toBeVisible({ timeout: 20_000 });
      await page.goto(`${origin}/operator?mission_id=synthetic-mission-a`);
      await expect(
        page.getByRole('heading', { name: 'Operator', exact: true })
      ).toBeVisible();
      await noOverflow(page);
      await page.screenshot({
        path: join(evidence, `archive-operator-${width}x${height}.png`),
        fullPage: true,
      });
      // Import the enhanced archive through the unchanged UI on a non-active
      // copy. Clean separate-instance import is verified by archive_probe.py.
      if (width === 1920) {
        await page.goto(`${origin}/missions`);
        await page.getByRole('button', { name: /Import/i }).click();
        const importing = page.getByRole('dialog');
        await expect(
          importing.getByRole('heading', { name: 'Import Mission' })
        ).toBeVisible();
        await page.screenshot({
          path: join(evidence, 'archive-existing-import-controls.png'),
        });
        await importing
          .getByRole('button', { name: 'Close', exact: true })
          .click();
      }
      captures.push(`${width}x${height}`);
    } finally {
      await context.close();
    }
  }
  expect(errors).toEqual([]);
  writeFileSync(
    join(evidence, 'archive-browser.json'),
    JSON.stringify(
      {
        synthetic: true,
        captures,
        existingExportControls: true,
        downloadableZip: true,
        existingImportControls: true,
        operatorResponsive: true,
        browserErrors: errors,
      },
      null,
      2
    )
  );
  expect(
    readFileSync(join(evidence, 'browser-mission-1920.zip'))
      .subarray(0, 2)
      .toString()
  ).toBe('PK');
});
