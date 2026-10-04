import { writeFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import {
  installOverviewWindowFixture,
  retainedHistoryTimes,
} from './support/overview-window-fixture';
import { observeOverviewCamera } from './support/overview-camera';

for (const fullscreen of [false, true]) {
  test(`controlled link saves, GPS loss/recovery and browser camera preference converge in ${fullscreen ? 'native fullscreen' : 'ordinary'} Overview`, async ({
    context,
  }, info) => {
    const fixture = await installOverviewWindowFixture(context);
    const timings: Record<string, number> = {};
    const overview = await context.newPage();
    await observeOverviewCamera(overview);
    await overview.goto('/overview');
    await expect(overview.getByLabel('Globe legend')).toContainText(
      'Aircraft',
      { timeout: 20000 }
    );
    if (fullscreen) {
      await overview
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() => overview.evaluate(() => !!document.fullscreenElement))
        .toBe(true);
    }
    const canvas = await overview
      .locator('.overview-globe canvas')
      .elementHandle();
    const editing = await context.newPage();
    await editing.goto('/configuration');
    await editing.bringToFront();
    try {
      await expect(overview.getByLabel('Globe legend')).toContainText(
        'Traffic path'
      );
      const save = editing.waitForResponse(
        (r) =>
          r.url().endsWith('/api/overview-links/settings') &&
          r.request().method() === 'PUT'
      );
      await editing
        .getByRole('switch', { name: 'Starshield data link' })
        .click();
      expect((await save).status()).toBe(200);
      const linkAt = Date.now();
      await expect(overview.getByLabel('Globe legend')).not.toContainText(
        'Traffic path',
        { timeout: 8000 }
      );
      timings.linkSave = Date.now() - linkAt;
      expect(fixture.state.links.starshield_link_enabled).toBe(false);
      await editing.getByLabel('Follow aircraft on Overview').check();
      await expect(
        overview.getByText('Following aircraft', { exact: true })
      ).toBeVisible({ timeout: 8000 });
      Object.assign(fixture.state, { positionAvailable: false });
      const gpsAt = Date.now();
      await expect(
        overview.getByText('Follow paused · Aircraft position unavailable', {
          exact: true,
        })
      ).toBeVisible({ timeout: 8000 });
      timings.gpsLoss = Date.now() - gpsAt;
      await expect(
        overview
          .getByLabel('Globe legend')
          .getByText('Aircraft', { exact: true })
      ).toHaveCount(0);
      Object.assign(fixture.state, { positionAvailable: true });
      const recoveredAt = Date.now();
      await expect(
        overview.getByText('Following aircraft', { exact: true })
      ).toBeVisible({ timeout: 8000 });
      timings.gpsRecovery = Date.now() - recoveredAt;
      await expect(overview.getByLabel('Globe legend')).toContainText(
        'Aircraft'
      );
      await editing.getByLabel('Follow aircraft on Overview').uncheck();
      await expect(
        overview.getByText('Following aircraft', { exact: true })
      ).toHaveCount(0);
      for (const value of Object.values(timings))
        expect(value).toBeLessThanOrEqual(8000);
      expect(
        await canvas!.evaluate(
          (node) => node === document.querySelector('.overview-globe canvas')
        )
      ).toBe(true);
      expect(await retainedHistoryTimes(overview)).toContain(fixture.marker);
      expect(await overview.evaluate(() => !!document.fullscreenElement)).toBe(
        fullscreen
      );
      expect(await editing.evaluate(() => document.hasFocus())).toBe(true);
      await overview.screenshot({ path: info.outputPath('saved-paths.png') });
    } finally {
      await writeFile(
        info.outputPath('controlled-path-evidence.json'),
        JSON.stringify(
          {
            fixtures: true,
            timings,
            reads: fixture.readCounts,
            requestLog: fixture.requestLog,
          },
          null,
          2
        )
      );
    }
  });
}
