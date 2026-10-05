import { expect, test } from '@playwright/test';
import { installAdsbFixture, freshContact } from './support/adsb-fixture';
import { adsbSettings } from '../../src/test/adsb-fixtures';

const evidence = '../../docs/reports/evidence/2026-10-05-configuration';

test('Traffic exposes aircraft identity and hex-only updates in a wide workspace', async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const fixture = await installAdsbFixture(context);
  fixture.setSettings(
    adsbSettings({
      include_hexes: ['AE1234', 'A1B2C3'],
      exclude_hexes: ['AE9999', 'AE9902'],
      callsign_substrings: ['RCH', 'SAM', 'DUKE'],
    })
  );
  fixture.setContacts([
    freshContact({
      hex: 'AE1234',
      callsign: 'RCH042',
      registration: '07-7180',
      aircraft_type: 'C17',
      ground_speed_knots: 452,
    }),
    freshContact({
      hex: 'A1B2C3',
      callsign: 'N513QS',
      registration: 'N513QS',
      aircraft_type: 'C56X',
      military: false,
      altitude: { value: 41000, unit: 'ft', source: 'barometric' },
      ground_speed_knots: 427,
    }),
    freshContact({
      hex: 'AE5678',
      callsign: 'SAM215',
      registration: '09-0540',
      aircraft_type: 'B737',
      altitude: { value: 35000, unit: 'ft', source: 'barometric' },
    }),
    freshContact({
      hex: 'AE8801',
      callsign: 'DUKE71',
      registration: '12-3050',
      aircraft_type: 'BE20',
      altitude: { value: 18000, unit: 'ft', source: 'geometric' },
      ground_speed_knots: 238,
      position_observed_at_ms: Date.now() - 40000,
    }),
    freshContact({
      hex: 'AE9902',
      callsign: 'RCH806',
      registration: null,
      aircraft_type: 'C5M',
      altitude: null,
      ground_speed_knots: null,
    }),
  ]);
  await page.goto('/configuration');
  await page
    .getByRole('tab', { name: 'Aircraft Traffic', exact: true })
    .click();
  const table = page.getByRole('table');
  await expect(table.getByRole('row')).toHaveCount(6);
  for (const name of [
    'Callsign',
    'Registration',
    'Aircraft type',
    'ICAO hex',
    'Altitude',
    'Ground speed',
    'Position age',
    'Selection',
    'Actions',
  ])
    await expect(
      table.getByRole('columnheader', { name, exact: true })
    ).toBeVisible();
  await expect(page.getByText('AE1234 · RCH042 · 07-7180 · C17')).toBeVisible();
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue(
    'AE1234\nA1B2C3'
  );
  await expect(
    page
      .getByRole('region', { name: 'Saved excluded aircraft' })
      .locator('li')
      .filter({ hasText: 'AE9999' })
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Fullscreen', exact: true })
  ).toHaveCount(0);
  const bounds = await table.boundingBox();
  expect(bounds!.width).toBeGreaterThan(1000);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth
    )
  ).toBe(true);
  await page.screenshot({ path: `${evidence}/traffic-1920x1080.png` });

  // Context labels never enter the persistence payload.
  const update = page.waitForRequest(
    (request) =>
      request.method() === 'PUT' &&
      request.url().endsWith('/api/overview-adsb/settings')
  );
  await page.getByRole('button', { name: 'Include AE5678' }).click();
  expect((await update).postDataJSON()).toEqual({
    include_hexes: ['AE1234', 'A1B2C3', 'AE5678'],
  });
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue(
    'AE1234\nA1B2C3\nAE5678'
  );
});

test('compact navigation keeps list drafts and table scrolling contained', async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await installAdsbFixture(context);
  fixture.setSettings(adsbSettings());
  fixture.setContacts([freshContact()]);
  await page.goto('/configuration');
  await page
    .getByRole('tab', { name: 'Aircraft Traffic', exact: true })
    .click();
  await page.getByLabel('Included ICAO hexes').fill('00AB12');
  await page.getByRole('tab', { name: 'Displays' }).click();
  await expect(
    page.getByRole('button', { name: 'Recenter view' })
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Open Overview' })
  ).toBeVisible();
  await page
    .getByRole('tab', { name: 'Aircraft Traffic', exact: true })
    .click();
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('00AB12');
  const scroller = page.getByRole('table').locator('..');
  expect(
    await scroller.evaluate((node) => node.scrollWidth > node.clientWidth)
  ).toBe(true);
  await scroller.evaluate((node) => {
    node.scrollLeft = node.scrollWidth;
  });
  await page
    .getByRole('button', { name: 'Exclude 00AB12' })
    .scrollIntoViewIfNeeded();
  await expect(
    page.getByRole('button', { name: 'Exclude 00AB12' })
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth
    )
  ).toBe(true);
  await page.screenshot({ path: `${evidence}/traffic-mobile.png` });
});

test('keyboard navigation exposes diagnostics and preserves clock drafts', async ({
  page,
  context,
}) => {
  await installAdsbFixture(context);
  await page.goto('/configuration');
  await page.getByLabel('Clock 1 label').fill('Unsubmitted clock');
  await page.getByRole('tab', { name: 'Overview', exact: true }).focus();
  await page.keyboard.press('End');
  await expect(
    page.getByRole('tab', { name: 'Diagnostics', exact: true })
  ).toHaveAttribute('aria-selected', 'true');
  await expect(
    page.getByRole('region', { name: 'Overview map diagnostics' })
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Orbital traffic diagnostics' })
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'ADS-B source status' })
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'ADS-B aircraft settings' })
  ).toHaveCount(0);
  await page.keyboard.press('Home');
  await expect(page.getByLabel('Clock 1 label')).toHaveValue(
    'Unsubmitted clock'
  );
});

test('aircraft search is independent of Overview mode and the bounded list scrolls by keyboard', async ({
  page,
  context,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const fixture = await installAdsbFixture(context);
  fixture.setSettings(
    adsbSettings({
      mode: 'included_only',
      include_hexes: ['000001'],
      exclude_hexes: ['000002'],
      callsign_substrings: ['NONE'],
    })
  );
  fixture.setContacts([
    freshContact({ hex: '000001', aircraft_type: 'C560' }),
    freshContact({ hex: '000002', aircraft_type: 'C560' }),
    freshContact({ hex: '3C5602', aircraft_type: 'B738' }),
    ...Array.from({ length: 40 }, (_, i) =>
      freshContact({
        hex: (i + 256).toString(16).toUpperCase().padStart(6, '0'),
        callsign: `RCH${i}`,
      })
    ),
  ]);
  await page.goto('/configuration');
  await page
    .getByRole('tab', { name: 'Aircraft Traffic', exact: true })
    .click();
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(44);
  await expect(page.getByRole('row', { name: /000001/ })).toContainText(
    'Included'
  );
  await expect(page.getByRole('row', { name: /000002/ })).toContainText(
    'Excluded'
  );
  await expect(page.getByRole('row', { name: /3C5602/ })).toContainText(
    'Not selected'
  );
  const list = page.getByRole('region', { name: 'Aircraft list', exact: true });
  expect(
    await list.evaluate(
      (node) =>
        node.clientHeight <= 384 && node.scrollHeight > node.clientHeight
    )
  ).toBe(true);
  await list.focus();
  await page.keyboard.press('PageDown');
  await expect
    .poll(() => list.evaluate((node) => node.scrollTop))
    .toBeGreaterThan(0);
  const search = page.getByRole('searchbox', { name: 'Search aircraft' });
  await search.fill('c560');
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(4);
  await expect(page.getByRole('row', { name: /3C5602/ })).toBeVisible();
  await search.fill('rch0');
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(2);
  await expect(page.getByLabel('ADS-B mode')).toHaveValue('included_only');
  const selected = await page.evaluate(async () =>
    (await fetch('/api/overview-adsb/traffic')).json()
  );
  expect(
    selected.contacts.map((contact: { hex: string }) => contact.hex)
  ).toEqual(['000001']);
  await page.getByRole('tab', { name: 'Network Traffic', exact: true }).click();
  await expect(
    page.getByRole('switch', { name: 'Starshield data link' })
  ).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'ADS-B aircraft settings' })
  ).toHaveCount(0);
  await page.getByRole('tab', { name: 'Displays', exact: true }).click();
  await expect(
    page.getByRole('switch', { name: 'Use GPS Location' })
  ).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Recenter view' })
  ).toBeVisible();
  await page
    .getByRole('tab', { name: 'Terminal Controls', exact: true })
    .click();
  await expect(
    page.getByRole('switch', { name: 'Use GPS Location' })
  ).toBeVisible();
  await page.getByRole('tab', { name: 'Overview', exact: true }).click();
  const follow = page.getByRole('switch', {
    name: 'Follow aircraft on Overview',
  });
  await follow.focus();
  await page.keyboard.press('Space');
  await expect(follow).toBeChecked();
  await expect(
    page.getByRole('group', { name: 'Clock 1', exact: true })
  ).toBeVisible();
});

test('aircraft Include and Exclude buttons toggle membership without changing the other list', async ({
  page,
  context,
}) => {
  const fixture = await installAdsbFixture(context);
  fixture.setSettings(
    adsbSettings({
      mode: 'included_only',
      include_hexes: ['00AB12'],
      exclude_hexes: ['00AB12'],
    })
  );
  fixture.setContacts([freshContact()]);
  await page.goto('/configuration');
  await page
    .getByRole('tab', { name: 'Aircraft Traffic', exact: true })
    .click();
  const include = page.getByRole('button', { name: 'Include 00AB12' });
  const exclude = page.getByRole('button', { name: 'Exclude 00AB12' });
  const row = page.getByRole('row', { name: /00AB12/ });
  await expect(include).toHaveAttribute('aria-pressed', 'true');
  await expect(exclude).toHaveAttribute('aria-pressed', 'true');
  await expect(row).toContainText('Excluded');
  await include.focus();
  await page.keyboard.press('Space');
  await expect(include).toHaveAttribute('aria-pressed', 'false');
  await expect(exclude).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('');
  await expect(row).toContainText('Excluded');
  await exclude.click();
  await expect(exclude).toHaveAttribute('aria-pressed', 'false');
  await expect(page.getByLabel('Excluded ICAO hexes')).toHaveValue('');
  await expect(row).toContainText('Not selected');
  await include.click();
  await expect(include).toHaveAttribute('aria-pressed', 'true');
  await expect(row).toContainText('Included');
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('00AB12');
  await exclude.click();
  await expect(exclude).toHaveAttribute('aria-pressed', 'true');
  await expect(include).toHaveAttribute('aria-pressed', 'true');
  await expect(row).toContainText('Excluded');
  await expect(page.getByLabel('Included ICAO hexes')).toHaveValue('00AB12');
  await expect(page.getByLabel('Excluded ICAO hexes')).toHaveValue('00AB12');
});
