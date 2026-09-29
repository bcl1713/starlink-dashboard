import { expect, test } from '@playwright/test';

const metrics = [
  'starlink_network_latency_ms_current',
  'starlink_network_throughput_down_mbps_current',
  'starlink_network_throughput_up_mbps_current',
  'starlink_network_packet_loss_percent',
  'starlink_dish_obstruction_percent',
];
const initial = Math.floor(Date.now() / 1000);
function bundle(end = initial, windowSeconds = 1800) {
  return {
    window_seconds: windowSeconds,
    start_timestamp_seconds: end - windowSeconds,
    end_timestamp_seconds: end,
    step_seconds: 5,
    series: Object.fromEntries(
      metrics.map((metric, index) => [
        metric,
        Array.from({ length: 5 }, (_, sample) => [
          end - 25 + sample * 5,
          index + sample + 1,
        ]),
      ])
    ),
    rolling_5m: Object.fromEntries(
      metrics.map((metric, index) => [
        metric,
        {
          state: 'available',
          min: Array.from({ length: 5 }, (_, sample) => [
            end - 25 + sample * 5,
            index + sample + 0.5,
          ]),
          avg: Array.from({ length: 5 }, (_, sample) => [
            end - 25 + sample * 5,
            index + sample + 1,
          ]),
          max: Array.from({ length: 5 }, (_, sample) => [
            end - 25 + sample * 5,
            index + sample + 1.5,
          ]),
        },
      ])
    ),
  };
}

test.describe('Overview metric history', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });
  test('fits five shared-query plots above POIs while preserving globe and legend', async ({
    page,
  }, testInfo) => {
    let requests = 0;
    const requestTimes: number[] = [];
    let end = initial;
    let windowSeconds = 1800;
    let fail = false;
    await page.route('**/api/overview-history', async (route) => {
      requests++;
      requestTimes.push(Date.now());
      if (fail)
        await route.fulfill({ status: 503, json: { detail: 'unavailable' } });
      else {
        end = Math.floor(Date.now() / 1000);
        await route.fulfill({ json: bundle(end, windowSeconds) });
      }
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      if (route.request().method() === 'PUT') {
        windowSeconds = (
          route.request().postDataJSON() as { window_seconds: number }
        ).window_seconds;
        end += 5;
      }
      await route.fulfill({ json: { window_seconds: windowSeconds } });
    });
    await page.route('**/api/overview/upcoming-pois', async (route) => {
      await route.fulfill({ json: { state: 'no_active_mission', pois: [] } });
    });
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({ json: { routes: [], total: 0 } });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: new Date(initial * 1000).toISOString(),
          network: { latency_ms: 42 },
        },
      });
    });
    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({ json: [] });
    });
    await page.route('**/api/active-x-link', async (route) => {
      await route.fulfill({ json: { satellite_id: null } });
    });
    await page.route('**/api/overview-clocks/settings', async (route) => {
      await route.fulfill({
        json: {
          clocks: [
            { label: 'Zulu / UTC', time_zone: 'UTC' },
            { label: 'Washington, DC', time_zone: 'America/New_York' },
            { label: 'Omaha, NE', time_zone: 'America/Chicago' },
            { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
          ],
        },
      });
    });
    const texture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.ok()
    );
    await page.goto('/overview', { waitUntil: 'commit' });
    await expect(texture).resolves.toBeTruthy();
    const canvas = page.locator('.overview-page canvas').last();
    await expect(canvas).toBeVisible();
    await page.evaluate(
      () =>
        new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    );
    const graphs = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(graphs).toHaveCount(5);
    await expect(graphs.locator('.uplot')).toHaveCount(5);
    const settledRequests = requests;
    expect(settledRequests).toBeGreaterThanOrEqual(1);
    const pois = await page.getByLabel('Upcoming POIs').boundingBox();
    const top = await page.locator('.overview-metrics').boundingBox();
    const legend = await page.getByLabel('Globe legend').boundingBox();
    await page.screenshot({
      path: testInfo.outputPath('overview-history-1920x1080.png'),
      animations: 'disabled',
    });
    for (const panel of await graphs.all()) {
      const box = await panel.boundingBox();
      expect(box && pois && box.y + box.height <= pois.y).toBeTruthy();
      expect(box && top && box.y >= top.y + top.height).toBeTruthy();
      expect(box && box.y >= 0 && box.y + box.height <= 1080).toBeTruthy();
      expect(box && legend && box.x + box.width <= legend.x).toBeTruthy();
      await expect(panel.getByText('Observed')).toBeVisible();
      await expect(panel.getByText('Low (5m)')).toBeVisible();
      await expect(panel.getByText('Average (5m)')).toBeVisible();
      await expect(panel.getByText('High (5m)')).toBeVisible();
      expect(
        await panel.evaluate((node) => node.scrollHeight <= node.clientHeight)
      ).toBe(true);
    }
    await expect(canvas).toBeVisible();
    expect(
      await canvas.evaluate(
        (node) => document.elementFromPoint(960, 570) === node
      )
    ).toBe(true);
    await page.mouse.move(960, 570);
    await page.mouse.down();
    await page.mouse.move(1100, 610, { steps: 8 });
    await page.mouse.up();
    await expect(page.getByLabel('Globe legend')).toBeVisible();

    const axis = graphs
      .first()
      .locator('.overview-metric-history__time-axis span:last-child');
    const surface = graphs.first().locator('.overview-metric-history__surface');
    const left = async () =>
      surface.evaluate(
        (node) => new DOMMatrix(getComputedStyle(node).transform).m41
      );
    const initialOffset = await left();
    const before = await axis.textContent();
    await expect
      .poll(() => left(), { timeout: 8_000 })
      .toBeLessThan(initialOffset);
    await expect
      .poll(() => axis.textContent(), { timeout: 8_000 })
      .not.toBe(before);
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(settledRequests);
    // Every scheduled tick issues one GET, not five child-panel requests.
    for (let index = 1; index < requestTimes.length; index++)
      expect(
        requestTimes[index] - requestTimes[index - 1]
      ).toBeGreaterThanOrEqual(4_000);
    const beforeWindow = requests;
    const beforeWindowAxis = await graphs
      .first()
      .locator('.overview-metric-history__time-axis span:first-child')
      .textContent();
    await page.getByLabel('Aircraft history window').selectOption('900');
    await expect.poll(() => requests).toBeGreaterThan(beforeWindow);
    await expect
      .poll(() =>
        graphs
          .first()
          .locator('.overview-metric-history__time-axis span:first-child')
          .textContent()
      )
      .not.toBe(beforeWindowAxis);
    await expect(graphs.first().getByRole('status')).toHaveText(
      'History available'
    );
    fail = true;
    const beforeFailure = requests;
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(beforeFailure);
    await expect(graphs.first().getByRole('status')).toContainText(
      'Last-known history; refresh unavailable'
    );
  });

  test('reflows as a single non-overlapping column at 44rem', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 704, height: 1080 });
    await page.route('**/api/overview-history', async (route) => {
      await route.fulfill({ json: bundle() });
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      await route.fulfill({ json: { window_seconds: 1800 } });
    });
    await page.goto('/overview', { waitUntil: 'commit' });
    const panels = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(panels).toHaveCount(5);
    const pois = await page.getByLabel('Upcoming POIs').boundingBox();
    for (const panel of await panels.all()) {
      const box = await panel.boundingBox();
      expect(box && pois && box.y + box.height <= pois.y).toBeTruthy();
    }
  });
});
