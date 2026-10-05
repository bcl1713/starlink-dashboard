import { expect, test } from '@playwright/test';
import { adsbSettings } from '../../src/test/adsb-fixtures';
import {
  freshContact,
  installAdsbFixture,
  observeAdsbScene,
} from './support/adsb-fixture';
import {
  expectSameCamera,
  settledOverviewCamera,
} from './support/overview-camera';

test('shared saves converge across windows, obsolete replies cannot restore exclusions and failed saves keep confirmation', async ({
  context,
}, info) => {
  const fixture = await installAdsbFixture(context);
  fixture.setContacts([
    freshContact(),
    freshContact({
      hex: '000001',
      military: false,
      callsign: null,
      registration: 'CIVIL',
      latitude: 40,
      longitude: -92,
    }),
  ]);
  const overview = await context.newPage();
  await observeAdsbScene(overview);
  await overview.goto('/overview');
  const before = await settledOverviewCamera(overview);
  const editing = await context.newPage();
  await editing.goto('/configuration');
  await editing.getByRole('switch', { name: 'ADS-B aircraft layer' }).click();
  const start = Date.now();
  await expect(
    overview.getByRole('button', { name: 'Details for 00AB12' })
  ).toBeVisible({ timeout: 5500 });
  const enableConvergenceMs = Date.now() - start;
  await editing.getByLabel('Included ICAO hexes').fill('000001');
  await editing
    .getByRole('button', { name: 'Save included aircraft', exact: true })
    .click();
  await expect(overview.locator('[data-adsb-label="000001"]')).toBeVisible({
    timeout: 5500,
  });
  const held = fixture.holdNextTraffic();
  await overview.waitForRequest('**/api/overview-adsb/traffic');
  await editing.getByLabel('Excluded ICAO hexes').fill('00AB12,000001');
  await editing
    .getByRole('button', { name: 'Save excluded aircraft', exact: true })
    .click();
  await expect(
    overview.getByText('ADS-B aircraft', { exact: true })
  ).toHaveCount(0, { timeout: 5500 });
  held.release();
  await expect(
    overview.getByRole('button', { name: 'Details for 000001' })
  ).toHaveCount(0);
  await expect(
    editing.getByRole('region', { name: 'Saved included aircraft' })
  ).toContainText('000001');
  fixture.failSettingsSave(true);
  await editing.getByRole('switch', { name: 'ADS-B aircraft layer' }).click();
  await expect(
    editing.getByRole('alert').filter({ hasText: 'ADS-B' })
  ).toBeVisible();
  await expect(
    editing.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).toBeChecked();
  fixture.failSettingsSave(false);
  await editing.reload();
  await expect(editing.getByLabel('Excluded ICAO hexes')).toHaveValue(
    '00AB12\n000001'
  );
  await editing.getByLabel('ADS-B mode').selectOption('included_only');
  await editing.getByLabel('Included ICAO hexes').fill('');
  await editing
    .getByRole('button', { name: 'Save included aircraft', exact: true })
    .click();
  await expect(
    overview.getByText('ADS-B aircraft', { exact: true })
  ).toHaveCount(0);
  await editing.getByRole('switch', { name: 'ADS-B aircraft layer' }).click();
  await expect(
    overview.getByRole('button', { name: /Details for/ })
  ).toHaveCount(0);
  expectSameCamera(before, await settledOverviewCamera(overview));
  await info.attach('cross-window-timing', {
    body: JSON.stringify({ enableConvergenceMs }),
    contentType: 'application/json',
  });
});

test('disabled held response and mission activation preserve saved aircraft settings', async ({
  context,
}) => {
  const fixture = await installAdsbFixture(context);
  fixture.setSettings(adsbSettings({ include_hexes: ['00AB12'] }));
  fixture.setContacts([freshContact()]);
  const page = await context.newPage();
  await page.goto('/configuration');
  await expect(page.getByRole('row', { name: /00AB12/ })).toBeVisible();
  const held = fixture.holdNextTraffic();
  await page.waitForRequest('**/api/overview-adsb/traffic');
  await page.getByRole('switch', { name: 'ADS-B aircraft layer' }).click();
  held.release();
  await expect(page.getByRole('row', { name: /00AB12/ })).toHaveCount(0);
  expect(
    await page.evaluate(
      async () =>
        (
          await fetch('/api/v2/missions/window-mission/legs/leg-a/activate', {
            method: 'POST',
          })
        ).status
    )
  ).toBe(200);
  await page.reload();
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('00AB12');
  await expect(
    page.getByRole('switch', { name: 'ADS-B aircraft layer' })
  ).not.toBeChecked();
});
