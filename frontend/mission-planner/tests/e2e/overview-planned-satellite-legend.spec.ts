import { expect, test, type Page } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

test.use({ video: 'on' });
async function planningFixture(page: Page) {
  let selection: { satellite_id: string | null; state?: string } = {
    satellite_id: 'X-6',
    state: 'normal',
  };
  let selectionError = false;
  let routeError = false;
  let catalog: unknown[] = [
    { satellite_id: 'X-6', transport: 'X', longitude: -50 },
  ];
  let windowSeconds = 300;
  const clocks = [
    'UTC',
    'America/New_York',
    'America/Chicago',
    'America/Los_Angeles',
  ].map((time_zone, i) => ({ label: `Clock ${i + 1}`, time_zone }));
  const now = '2026-10-02T00:00:00Z';
  await page.clock.install({ time: new Date(now) });
  await page.route('**/api/**', async (route) => {
    const endpoint = new URL(route.request().url()).pathname;
    if (endpoint === '/api/active-x-link')
      return route.fulfill({
        status: selectionError ? 503 : 200,
        json: selectionError ? { detail: 'unavailable' } : selection,
      });
    if (endpoint === '/api/satellites') return route.fulfill({ json: catalog });
    if (endpoint === '/api/routes')
      return route.fulfill({
        status: routeError ? 503 : 200,
        json: routeError
          ? { detail: 'unavailable' }
          : { routes: [{ id: 'route', is_active: true }], total: 1 },
      });
    if (endpoint === '/api/routes/route')
      return route.fulfill({
        json: {
          id: 'route',
          name: 'Planned route',
          points: [
            { latitude: 0, longitude: -50 },
            { latitude: 10, longitude: -40 },
          ],
        },
      });
    if (endpoint === '/api/overview-clocks/settings')
      return route.fulfill({ json: { clocks } });
    if (endpoint === '/api/status')
      return route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: { latitude: 0, longitude: -50, altitude: 35000 },
          ground_entry_point: { latitude: 2, longitude: -48 },
        },
      });
    if (endpoint === '/api/overview-history/settings') {
      if (route.request().method() === 'PUT')
        windowSeconds = route.request().postDataJSON().window_seconds;
      return route.fulfill({ json: { window_seconds: windowSeconds } });
    }
    if (endpoint === '/api/overview-history')
      return route.fulfill({
        json: {
          window_seconds: windowSeconds,
          start_timestamp_seconds: 1790898900,
          end_timestamp_seconds: 1790899200,
          step_seconds: 5,
          series: {
            starlink_dish_latitude_degrees: [
              [1, 0],
              [2, 1],
            ],
            starlink_dish_longitude_degrees: [
              [1, -50],
              [2, -49],
            ],
          },
        },
      });
    if (endpoint === '/api/overview/upcoming-pois')
      return route.fulfill({ json: { state: 'no_active_mission', pois: [] } });
    return route.fulfill({ json: {} });
  });
  return {
    select: (value: typeof selection) => {
      selection = value;
    },
    failSelection: () => {
      selectionError = true;
    },
    failRoute: () => {
      routeError = true;
    },
    catalog: (value: unknown[]) => {
      catalog = value;
    },
  };
}

test('keeps selection planning-only and conditional layers honest through errors', async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const fixture = await planningFixture(page);
  const texture = page.waitForResponse(
    (response) => response.url().endsWith('/earth-day-hi.jpg') && response.ok()
  );
  await page.goto('/overview');
  await waitForGlobeVisualReady(page, texture);
  const legend = page.getByLabel('Globe legend');
  const card = page.getByRole('region', { name: 'Planned satellite' });
  await expect(legend.locator('li')).toHaveText([
    'Aircraft',
    'Planned route',
    'Track history',
    'Ground entry point',
    'Planned satellite link',
  ]);
  await expect(card).toHaveText('X-BANDX-6PLANNED SATELLITE');
  await expect(card.locator('img, svg, time, [role="status"]')).toHaveCount(0);
  await expect(legend.getByRole('combobox')).toHaveCount(0);
  const track = legend.locator('.globe-legend__route--history');
  const link = legend.locator('.globe-legend__route--planned-link');
  const height = (node: HTMLElement) =>
    parseFloat(getComputedStyle(node).height);
  expect(await link.evaluate(height)).toBeGreaterThan(
    await track.evaluate(height)
  );
  const normalColor = await link.evaluate(
    (node) => getComputedStyle(node).backgroundColor
  );
  fixture.select({ satellite_id: 'X-6', state: 'warning' });
  await expect(page.getByLabel('Map status')).toContainText(
    'Planned link warning'
  );
  await expect
    .poll(() => link.evaluate((node) => getComputedStyle(node).backgroundColor))
    .not.toBe(normalColor);
  await expect(card).toHaveText('X-BANDX-6PLANNED SATELLITE');
  await page.getByRole('button', { name: 'Enter fullscreen overview' }).click();
  await page.screenshot({
    path: testInfo.outputPath('warning-fullscreen.png'),
  });
  fixture.failSelection();
  await expect(card).toContainText('UNAVAILABLE');
  await expect(page.getByLabel('Map status')).toContainText(
    'Last-known planned link warning'
  );
  await expect(legend.getByText('Planned satellite link')).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('cached-selection-failure.png'),
  });
  await page.evaluate(() => document.exitFullscreen());
  fixture.failRoute();
  await page.reload();
  await expect(page.getByLabel('Map status')).toContainText(
    'Unable to load the active route.',
    { timeout: 15000 }
  );
  await expect(legend.getByText('Aircraft', { exact: true })).toBeVisible();
  await expect(legend.getByText('Ground entry point')).toBeVisible();
  await expect(legend.getByText('Planned route')).toHaveCount(0);
});

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
  { width: 844, height: 390 },
  { width: 360, height: 800 },
]) {
  test(`contains planning overlays at ${viewport.width}x${viewport.height}`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize(viewport);
    const fixture = await planningFixture(page);
    fixture.select({ satellite_id: null });
    const texture = page.waitForResponse(
      (response) =>
        response.url().endsWith('/earth-day-hi.jpg') && response.ok()
    );
    await page.goto('/overview');
    await waitForGlobeVisualReady(page, texture);
    const card = page.getByRole('region', { name: 'Planned satellite' });
    await expect(card).toContainText('NO SATELLITE SELECTED');
    await expect(
      page.getByLabel('Globe legend').getByText('Planned satellite link')
    ).toHaveCount(0);
    if (viewport.width === 1920)
      await page
        .getByRole('button', { name: 'Enter fullscreen overview' })
        .click();
    await page.screenshot({ path: testInfo.outputPath('no-selection.png') });
    await page.addStyleTag({ content: 'html { font-size: 20px; }' });
    await expect
      .poll(() =>
        page
          .locator('.overview-page')
          .evaluate((node) => node.scrollWidth <= node.clientWidth)
      )
      .toBe(true);
    const longId = 'X-LONG-CONFIGURED-PLANNING-SATELLITE-IDENTIFIER';
    fixture.select({ satellite_id: longId });
    await expect(card).toContainText(longId);
    await expect(page.getByLabel('Map status')).toContainText(
      'Planned link unavailable'
    );
    const boxes = await card.evaluate((node) => {
      const bounds = node.getBoundingClientRect();
      return [...node.children].map((child) => {
        const box = child.getBoundingClientRect();
        return box.right <= bounds.right && box.left >= bounds.left;
      });
    });
    expect(boxes).toEqual([true, true, true]);
    await page.screenshot({
      path: testInfo.outputPath('long-id-enlarged.png'),
    });
  });
}

test('retains the shared window through Configuration navigation', async ({
  page,
}) => {
  await planningFixture(page);
  await page.goto('/configuration');
  await expect(page.getByLabel('Overview history window')).toHaveValue('300');
  await page.getByLabel('Overview history window').selectOption('900');
  await expect(page.getByLabel('Overview history window')).toHaveValue('900');
  await expect(
    page.getByRole('region', { name: 'Overview map diagnostics' })
  ).toContainText('Selected planned satellite X-6');
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await expect(page.getByLabel('Network history context')).toContainText(
    'LAST 15 MIN'
  );
  await expect(
    page.getByLabel('Globe legend').getByRole('combobox')
  ).toHaveCount(0);
});

for (const viewport of [
  { width: 1920, height: 1080 },
  { width: 390, height: 844 },
]) {
  test(`keeps Configuration navigation reachable above the globe at ${viewport.width}px`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await planningFixture(page);
    await page.goto('/overview');
    await expect(page.getByLabel('Globe legend')).toBeAttached();
    if (viewport.width < 768)
      await page.getByRole('button', { name: 'Toggle navigation' }).click();
    const navigation = page.getByRole('navigation', {
      name: 'Primary navigation',
    });
    const link = navigation.getByRole('link', {
      name: 'Configuration',
      exact: true,
    });
    const hitTarget = await link.evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return node.contains(
        document.elementFromPoint(
          rect.x + rect.width / 2,
          rect.y + rect.height / 2
        )
      );
    });
    expect(hitTarget).toBe(true);
    await link.click();
    await expect(page.getByLabel('Overview history window')).toBeVisible();
  });
}

test('retains the selected ID through invalid catalog geometry and recovers the link', async ({
  page,
}) => {
  const fixture = await planningFixture(page);
  fixture.catalog([{ satellite_id: 'X-6', transport: 'X', longitude: null }]);
  const texture = page.waitForResponse(
    (response) => response.url().endsWith('/earth-day-hi.jpg') && response.ok()
  );
  await page.goto('/overview');
  await waitForGlobeVisualReady(page, texture);
  await expect(
    page.getByRole('region', { name: 'Planned satellite' })
  ).toHaveText('X-BANDX-6PLANNED SATELLITE');
  await expect(page.getByLabel('Map status')).toContainText(
    'Planned link unavailable'
  );
  await expect(
    page.getByLabel('Globe legend').getByText('Planned satellite link')
  ).toHaveCount(0);
  fixture.catalog([{ satellite_id: 'X-6', transport: 'X', longitude: -50 }]);
  await page.reload();
  await expect(
    page.getByLabel('Globe legend').getByText('Planned satellite link')
  ).toBeVisible();
  await expect(page.getByLabel('Map status')).not.toContainText(
    'Planned link unavailable'
  );
  await expect(page.getByLabel('Configured map satellites')).toContainText(
    'X-6'
  );
});
