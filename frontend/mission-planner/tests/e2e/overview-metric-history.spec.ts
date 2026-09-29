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
  test('rebases painted samples across three five-second history polls', async ({
    page,
  }) => {
    test.setTimeout(120_000);
    const start = Math.floor(Date.now() / 1000);
    let requests = 0;
    let completed = 0;
    const observed: [number, number][] = Array.from(
      { length: 25 },
      (_, index) => [start - 125 + index * 5, index === 19 ? 90 : 10]
    );
    await page.route('**/api/overview-history/settings', (route) =>
      route.fulfill({ json: { window_seconds: 300 } })
    );
    await page.route('**/api/routes', (route) =>
      route.fulfill({ json: { routes: [], total: 0 } })
    );
    await page.route('**/api/overview/upcoming-pois', (route) =>
      route.fulfill({ json: { state: 'no_active_mission', pois: [] } })
    );
    await page.route('**/api/overview-clocks/settings', (route) =>
      route.fulfill({ json: { clocks: [] } })
    );
    await page.route('**/api/status', (route) =>
      route.fulfill({
        json: { timestamp: new Date(start * 1000).toISOString() },
      })
    );
    await page.route('**/api/satellites', (route) =>
      route.fulfill({ json: [] })
    );
    await page.route('**/api/active-x-link', (route) =>
      route.fulfill({ json: { satellite_id: null } })
    );
    await page.route('**/api/overview-history', async (route) => {
      const poll = requests++;
      // A request starts before its response can update the painted chart.
      if (poll === 1)
        await new Promise((resolve) => setTimeout(resolve, 1_000));
      if (poll > 0 && poll <= 3)
        observed.push([start + (poll - 1) * 5, 10 + poll * 10]);
      const end = start + poll * 5;
      await route.fulfill({
        json: {
          window_seconds: 300,
          start_timestamp_seconds: end - 300,
          end_timestamp_seconds: end,
          step_seconds: 5,
          series: { [metrics[0]]: observed },
          rolling_5m: {
            [metrics[0]]: {
              state: 'available',
              min: observed.map(([time]) => [time, 5]),
              avg: observed.map(([time]) => [time, 7]),
              max: observed.map(([time]) => [time, 9]),
            },
          },
        },
      });
      completed++;
    });
    await page.goto('/overview', { waitUntil: 'commit' });
    const panel = page.getByRole('region', { name: 'Network latency history' });
    const canvas = panel.locator('.uplot canvas').first();
    await expect(canvas).toBeVisible({ timeout: 20_000 });
    for (let poll = 0; poll <= 3; poll++) {
      const end = start + poll * 5;
      // The response and uPlot's queued canvas commit are separate events.
      // Keep both real-pixel oracles inside one bounded, per-bundle wait.
      await expect
        .poll(
          async () => {
            if (completed <= poll) return { spike: false, fresh: false };
            return canvas.evaluate(
              (node, { end, spike, time, value, freshRequired }) => {
                const el = node as HTMLCanvasElement;
                const image = el
                  .getContext('2d')!
                  .getImageData(0, 0, el.width, el.height);
                const isCyan = (x: number, y: number) => {
                  if (x < 0 || x >= el.width || y < 0 || y >= el.height)
                    return false;
                  const i = (y * el.width + x) * 4;
                  return (
                    image.data[i] < 170 &&
                    image.data[i + 1] > 175 &&
                    image.data[i + 2] > 185 &&
                    image.data[i + 3] > 0
                  );
                };
                const dpr = el.width / el.getBoundingClientRect().width;
                const expected = ((spike - (end - 307.5)) / 315) * el.width;
                let spikePainted = false;
                // The cyan observed peak alone reaches the top fifth.
                for (let y = 1; y < el.height / 5 && !spikePainted; y++)
                  for (let x = 0; x < el.width; x++)
                    if (isCyan(x, y) && Math.abs(x - expected) / dpr < 4) {
                      spikePainted = true;
                      break;
                    }
                if (!freshRequired) return { spike: spikePainted, fresh: true };
                // upper = ceil(peak * 1.1) = 100 for this fixture.
                const upper = Math.ceil(90 * 1.1);
                const x = Math.round(((time - (end - 307.5)) / 315) * el.width);
                const y = Math.round((1 - value / upper) * el.height);
                let freshPainted = false;
                for (let dy = -4; dy <= 4 && !freshPainted; dy++)
                  for (let dx = -4; dx <= 4; dx++)
                    if (isCyan(x + dx, y + dy)) {
                      freshPainted = true;
                      break;
                    }
                return { spike: spikePainted, fresh: freshPainted };
              },
              {
                end,
                spike: start - 30,
                time: start + (poll - 1) * 5,
                value: 10 + poll * 10,
                freshRequired: poll > 0,
              }
            );
          },
          {
            timeout: 30_000,
            message: `poll ${poll}: fulfilled bundle has rebased spike and arriving observed pixel`,
          }
        )
        .toEqual({ spike: true, fresh: true });
      // A later scheduled poll may finish during a slow pixel wait.
      expect(completed).toBeGreaterThanOrEqual(poll + 1);
    }
  });
  test('marks all five charts unavailable on the first failed fetch, then recovers', async ({
    page,
  }) => {
    let fail = true;
    let windowSeconds = 1800;
    await page.route('**/api/overview-history/settings', (route) => {
      if (route.request().method() === 'PUT')
        windowSeconds = (
          route.request().postDataJSON() as { window_seconds: number }
        ).window_seconds;
      return route.fulfill({ json: { window_seconds: windowSeconds } });
    });
    await page.route('**/api/overview-history', (route) =>
      fail
        ? route.fulfill({ status: 503, json: { detail: 'unavailable' } })
        : route.fulfill({
            json: bundle(Math.floor(Date.now() / 1000), windowSeconds),
          })
    );
    await page.goto('/overview', { waitUntil: 'commit' });
    const panels = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(panels).toHaveCount(5);
    await expect(panels.getByRole('status')).toHaveText(
      Array(5).fill('History unavailable')
    );
    await expect(panels.locator('.uplot')).toHaveCount(0);
    fail = false;
    await page.getByLabel('Aircraft history window').selectOption('900');
    await expect(panels.getByRole('status')).toHaveText(
      Array(5).fill('History available'),
      { timeout: 10_000 }
    );
    await expect(panels.locator('.uplot')).toHaveCount(5);
  });
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
    const top = await page.locator('.overview-clock-panel').boundingBox();
    const legend = await page.getByLabel('Globe legend').boundingBox();
    await page.screenshot({
      path: testInfo.outputPath('overview-history-1920x1080.png'),
      animations: 'disabled',
    });
    for (const panel of await graphs.all()) {
      const box = await panel.boundingBox();
      expect(box && pois && box.y + box.height <= pois.y).toBeTruthy();
      expect(
        box &&
          top &&
          (box.y >= top.y + top.height ||
            box.x + box.width <= top.x ||
            box.x >= top.x + top.width)
      ).toBeTruthy();
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
    const before = await axis.textContent();
    // A poll rebases the transform to zero; compare only within one bundle.
    await expect
      .poll(
        async () => {
          const bundleRequests = requests;
          const first = await left();
          await page.waitForTimeout(500);
          const second = await left();
          return requests === bundleRequests && second < first - 0.005;
        },
        { timeout: 12_000 }
      )
      .toBe(true);
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
    const plottedBeforeFailure = await graphs
      .first()
      .locator('.uplot canvas')
      .first()
      .evaluate((node) => (node as HTMLCanvasElement).toDataURL());
    fail = true;
    const beforeFailure = requests;
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(beforeFailure);
    await expect(graphs.first().getByRole('status')).toContainText(
      'Last-known history; refresh unavailable'
    );
    expect(
      await graphs
        .first()
        .locator('.uplot canvas')
        .first()
        .evaluate((node) => (node as HTMLCanvasElement).toDataURL())
    ).toBe(plottedBeforeFailure);
    fail = false;
    const beforeRecovery = requests;
    await expect
      .poll(() => requests, { timeout: 8_000 })
      .toBeGreaterThan(beforeRecovery);
    await expect(graphs.first().getByRole('status')).toHaveText(
      'History available'
    );
  });

  test('reflows legibly before two graph columns become cramped', async ({
    page,
  }) => {
    await page.route('**/api/overview-history', async (route) => {
      await route.fulfill({ json: bundle() });
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      await route.fulfill({ json: { window_seconds: 1800 } });
    });
    await page.setViewportSize({ width: 800, height: 1080 });
    await page.goto('/overview', { waitUntil: 'commit' });
    const panels = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    await expect(panels).toHaveCount(5);
    for (const width of [800, 752, 705, 704]) {
      await page.setViewportSize({ width, height: 1080 });
      const pois = await page.getByLabel('Upcoming POIs').boundingBox();
      const boxes = await Promise.all(
        (await panels.all()).map((panel) => panel.boundingBox())
      );
      expect(boxes.every((box) => box && box.width >= 300)).toBe(true);
      expect(
        boxes.every((box) => box && pois && box.y + box.height <= pois.y)
      ).toBe(true);
      expect(
        boxes.every(
          (box, index) =>
            index === 0 ||
            (box &&
              boxes[index - 1] &&
              box.y >= boxes[index - 1]!.y + boxes[index - 1]!.height)
        )
      ).toBe(true);
      expect(
        await page
          .locator('.overview-page')
          .evaluate((node) => getComputedStyle(node).overflowY)
      ).toBe('auto');
      await expect(panels.first().getByText('Observed')).toBeVisible();
    }
  });
});
