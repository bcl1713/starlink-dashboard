import { expect, test } from '@playwright/test';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import {
  adsbScene,
  freshContact,
  installAdsbFixture,
  observeAdsbScene,
} from './support/adsb-fixture';
import {
  expectSameCamera,
  settledOverviewCamera,
} from './support/overview-camera';

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
])
  test(`included identities, selection, focus and dialog fit ${viewport.width}x${viewport.height}`, async ({
    context,
  }, info) => {
    const fixture = await installAdsbFixture(context);
    const contacts = [
      freshContact({
        callsign:
          'VERY LONG COINCIDENT AIRCRAFT IDENTITY THAT MUST REMAIN VISIBLE',
      }),
      freshContact({
        hex: '000001',
        callsign: null,
        registration: 'REG-FALLBACK',
      }),
      freshContact({
        hex: '000002',
        callsign: null,
        registration: null,
        position_observed_at_ms: Date.now() - 40000,
      }),
      freshContact({ hex: '000003', latitude: -38, longitude: 90 }),
    ];
    fixture.setContacts(contacts);
    fixture.setSettings(
      adsbSettings({ include_hexes: contacts.slice(0, 3).map((c) => c.hex) })
    );
    const page = await context.newPage();
    await page.setViewportSize(viewport);
    await observeAdsbScene(page);
    await page.goto('/overview');
    await expect(page.locator('[data-adsb-label]')).toHaveCount(3);
    await expect(page.locator('[data-adsb-label="000002"]')).toContainText(
      '000002 · ◷ Stale'
    );
    await expect(page.locator('[data-adsb-label="000001"]')).toContainText(
      'REG-FALLBACK'
    );
    await expect(
      page.getByRole('button', { name: 'Details for 000003' })
    ).toHaveCount(0);
    const before = await settledOverviewCamera(page);
    const trigger = page.getByRole('button', { name: 'Details for 00AB12' });
    await trigger.focus();
    await trigger.press('Enter');
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText('Track');
    await expect(dialog).toContainText('30000 ft (barometric)');
    await expect(dialog.getByRole('button', { name: 'Include' })).toHaveCount(
      0
    );
    expect(
      await dialog.evaluate((node) => node.contains(document.activeElement))
    ).toBe(true);
    await page.screenshot({ path: info.outputPath('before-containment.png') });
    const bounds = await dialog.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height);
    await page.screenshot({ path: info.outputPath('details.png') });
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    expectSameCamera(before, await settledOverviewCamera(page));
    if (viewport.width === 1920) {
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
      await expect
        .poll(() => page.evaluate(() => !!document.fullscreenElement))
        .toBe(true);
      await trigger.focus();
      await trigger.press('Enter');
      await expect(dialog).toBeVisible();
      expect(
        await dialog.evaluate(
          (node) => !!document.fullscreenElement?.contains(node)
        )
      ).toBe(true);
      await page.screenshot({
        path: info.outputPath('fullscreen-details.png'),
      });
      await dialog.getByRole('button', { name: 'Close', exact: true }).click();
      await expect(trigger).toBeFocused();
      await settledOverviewCamera(page);
      const point = (await adsbScene(page)).batches
        .flatMap((b) => b.points)
        .find((p) => p.hex === '000001')!;
      await page.mouse.click(point.x, point.y);
      await expect(dialog).toBeVisible();
      await dialog.getByRole('button', { name: 'Close', exact: true }).click();
      await page.mouse.move(point.x, point.y);
      await page.mouse.down();
      await page.mouse.move(point.x + 25, point.y + 25);
      await page.mouse.move(point.x, point.y);
      await page.mouse.up();
      await expect(dialog).toHaveCount(0);
    }
    await page.screenshot({ path: info.outputPath('labels.png') });
  });

test('original observation age survives failures, repeated replies and foreground resume; selected expiry closes details', async ({
  context,
}) => {
  const fixture = await installAdsbFixture(context),
    now = Date.now();
  fixture.setContacts([freshContact({ position_observed_at_ms: now })]);
  fixture.setSettings(adsbSettings({ include_hexes: ['00AB12'] }));
  const page = await context.newPage();
  await observeAdsbScene(page);
  await page.clock.setFixedTime(now + 29999);
  await page.goto('/overview');
  const label = page.locator('[data-adsb-label="00AB12"]');
  await expect(label).toBeVisible();
  await expect(label).not.toContainText('Stale');
  fixture.failTraffic(true);
  await page.clock.setFixedTime(now + 30000);
  await expect(label).toContainText('◷ Stale');
  const trigger = page.getByRole('button', { name: 'Details for 00AB12' });
  await trigger.focus();
  await trigger.press('Enter');
  await expect(page.getByRole('dialog')).toContainText('Stale');
  await page.clock.setFixedTime(now + 119999);
  await expect(label).toHaveCount(1);
  await page.clock.setFixedTime(now + 120000);
  await expect(label).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  fixture.failTraffic(false);
  await page.clock.setFixedTime(now + 130000);
  await page.evaluate(() =>
    document.dispatchEvent(new Event('visibilitychange'))
  );
  await expect(label).toHaveCount(0);
  await page.waitForResponse('**/api/overview-adsb/traffic');
  await expect(label).toHaveCount(0);
  fixture.setContacts([
    freshContact({
      position_observed_at_ms: now + 130000,
      acquired_at_ms: now + 130000,
    }),
  ]);
  await expect(label).toBeVisible({ timeout: 5500 });
  await expect(label).not.toContainText('Stale');
  await page.goto('/configuration');
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('00AB12');
});
