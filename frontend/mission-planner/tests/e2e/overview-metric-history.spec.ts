import { expect, test } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

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
    await page.route('**/api/overview-history', (route) => {
      const poll = requests++;
      if (poll > 0 && poll <= 3)
        observed.push([start + (poll - 1) * 5, 10 + poll * 10]);
      const end = start + poll * 5;
      return route.fulfill({
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
    });
    await page.goto('/overview', { waitUntil: 'commit' });
    const panel = page.getByRole('region', { name: 'Network latency history' });
    const canvas = panel.locator('.uplot canvas').first();
    await expect(canvas).toBeVisible();
    for (let poll = 0; poll <= 3; poll++) {
      await expect
        .poll(() => requests, { timeout: 10_000 })
        .toBeGreaterThan(poll);
      const end = start + poll * 5;
      const expectedSpike = await canvas.evaluate(
        (node, { end, spike }) => {
          const el = node as HTMLCanvasElement;
          const surface = el.closest('.overview-metric-history__surface')!;
          const offset = new DOMMatrix(getComputedStyle(surface).transform).m41;
          const image = el
            .getContext('2d')!
            .getImageData(0, 0, el.width, el.height);
          const dpr = el.width / el.getBoundingClientRect().width;
          // The cyan observed peak alone reaches the top fifth of this plot.
          const painted: number[] = [];
          for (let y = 1; y < el.height / 5; y++)
            for (let x = 0; x < el.width; x++) {
              const i = (y * el.width + x) * 4;
              if (
                image.data[i] < 170 &&
                image.data[i + 1] > 175 &&
                image.data[i + 2] > 185 &&
                image.data[i + 3] > 0
              )
                painted.push(x / dpr + offset);
            }
          const expected =
            ((spike - (end - 307.5)) / 315) * el.getBoundingClientRect().width +
            offset;
          return { painted, expected };
        },
        { end, spike: start - 30 }
      );
      expect(
        expectedSpike.painted.length,
        `poll ${poll}: observed peak is painted`
      ).toBeGreaterThan(0);
      const nearest = expectedSpike.painted.reduce((best, x) =>
        Math.abs(x - expectedSpike.expected) <
        Math.abs(best - expectedSpike.expected)
          ? x
          : best
      );
      expect(
        Math.abs(nearest - expectedSpike.expected),
        `poll ${poll}: fixed timestamp stays at its rebased canvas coordinate`
      ).toBeLessThan(4);
      if (poll > 0) {
        const fresh = await canvas.evaluate(
          (node, { end, time, value }) => {
            const el = node as HTMLCanvasElement;
            const pixels = el
              .getContext('2d')!
              .getImageData(0, 0, el.width, el.height);
            const x = Math.round(((time - (end - 307.5)) / 315) * el.width);
            const y = Math.round((1 - value / 99) * el.height);
            for (let dy = -4; dy <= 4; dy++)
              for (let dx = -4; dx <= 4; dx++) {
                const i = ((y + dy) * el.width + x + dx) * 4;
                if (
                  pixels.data[i] < 170 &&
                  pixels.data[i + 1] > 175 &&
                  pixels.data[i + 2] > 185 &&
                  pixels.data[i + 3] > 0
                )
                  return true;
              }
            return false;
          },
          { end, time: start + (poll - 1) * 5, value: 10 + poll * 10 }
        );
        expect(
          fresh,
          `poll ${poll}: arriving observed value is painted at its timestamp`
        ).toBe(true);
      }
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

  test('fits populated plots and expanded five-row POIs together at 1920x1080', async ({
    page,
  }, testInfo) => {
    const now = Date.now();
    const names = [
      'AAR start',
      'Ka swap',
      'Ka entry',
      'X-band handoff',
      'RKSO',
    ];
    const kinds = [
      'aar_start',
      'ka_transition',
      'ka_coverage_entry',
      'x_band_transition',
      'arrival',
    ];
    await page.route('**/api/overview-history', (route) =>
      route.fulfill({ json: bundle(Math.floor(Date.now() / 1000)) })
    );
    await page.route('**/api/overview-history/settings', (route) =>
      route.fulfill({ json: { window_seconds: 1800 } })
    );
    await page.route('**/api/overview/upcoming-pois', (route) =>
      route.fulfill({
        json: {
          state: 'available',
          calculated_at: new Date(now).toISOString(),
          pois: names.map((name, index) => ({
            poi_id: `busy-${index}`,
            name,
            kind: kinds[index],
            latitude: 0,
            longitude: -50,
            expected_arrival_time: new Date(
              now + (index + 1) * 600_000
            ).toISOString(),
            estimated_arrival_time: new Date(
              now + (index + 1) * 600_000
            ).toISOString(),
            eta_seconds: (index + 1) * 600,
            eta_type: 'estimated',
            upcoming: true,
            map_retained: true,
          })),
        },
      })
    );
    await page.route('**/api/routes', (route) =>
      route.fulfill({ json: { routes: [], total: 0 } })
    );
    await page.route('**/api/status', (route) =>
      route.fulfill({
        json: {
          timestamp: new Date(now).toISOString(),
          network: { latency_ms: 42 },
        },
      })
    );
    await page.route('**/api/satellites', (route) =>
      route.fulfill({ json: [] })
    );
    await page.route('**/api/active-x-link', (route) =>
      route.fulfill({ json: { satellite_id: null } })
    );
    await page.route('**/api/overview-clocks/settings', (route) =>
      route.fulfill({
        json: {
          clocks: [
            { label: 'Zulu / UTC', time_zone: 'UTC' },
            { label: 'Washington, DC', time_zone: 'America/New_York' },
            { label: 'Omaha, NE', time_zone: 'America/Chicago' },
            { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
          ],
        },
      })
    );
    const texture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.ok()
    );
    await page.goto('/overview', { waitUntil: 'commit' });
    const globeCanvas = await waitForGlobeVisualReady(page, texture);
    expect(
      await globeCanvas.evaluate(
        (node) =>
          node ===
          [...document.querySelectorAll('.overview-page canvas')].at(-1)
      )
    ).toBe(true);
    const graphs = page
      .getByLabel('Overview metric history')
      .locator('[data-metric-panel]');
    const pois = page.getByLabel('Upcoming POIs');
    await expect(graphs.locator('.uplot')).toHaveCount(5);
    await expect(pois.locator('tbody tr')).toHaveCount(5);
    await expect(pois.locator('tbody tr')).toHaveText(
      names.map((name) => new RegExp(name))
    );
    await expect(pois.getByTestId('upcoming-pois-body')).toHaveCSS(
      'height',
      '224px'
    );
    const viewport = await page.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      dpr: devicePixelRatio,
    }));
    expect(viewport).toEqual({ width: 1920, height: 1080, dpr: 1 });
    const poiBox = await pois.boundingBox();
    const legendBox = await page.getByLabel('Globe legend').boundingBox();
    const metricsBox = await page
      .getByLabel('Current network metrics')
      .boundingBox();
    const clocksBox = await page.locator('.overview-clock-panel').boundingBox();
    expect(poiBox && poiBox.y + poiBox.height <= 1080).toBeTruthy();
    expect(
      poiBox && legendBox && poiBox.x + poiBox.width <= legendBox.x
    ).toBeTruthy();
    for (const panel of await graphs.all()) {
      const box = await panel.boundingBox();
      expect(box && poiBox && box.y + box.height <= poiBox.y).toBeTruthy();
      expect(box && legendBox && box.x + box.width <= legendBox.x).toBeTruthy();
      expect(
        box && metricsBox && box.x + box.width <= metricsBox.x
      ).toBeTruthy();
      expect(
        box && clocksBox && box.y >= clocksBox.y + clocksBox.height
      ).toBeTruthy();
      expect(box && box.width >= 200).toBeTruthy();
      for (const name of ['Observed', 'Low (5m)', 'Average (5m)', 'High (5m)'])
        await expect(panel.getByText(name)).toBeVisible();
      expect(
        await panel.evaluate((node) => node.scrollHeight <= node.clientHeight)
      ).toBe(true);
    }
    await page.screenshot({
      path: testInfo.outputPath('overview-history-busy-1920x1080.png'),
      animations: 'disabled',
    });
    const poiSizing = await pois.evaluate((node) => ({
      scroll: node.scrollHeight,
      client: node.clientHeight,
      rows: [...node.querySelectorAll('tbody tr')].map((row) => ({
        bottom: row.getBoundingClientRect().bottom,
        panelBottom: node.getBoundingClientRect().bottom,
      })),
    }));
    expect(poiSizing.scroll, JSON.stringify(poiSizing)).toBeLessThanOrEqual(
      poiSizing.client
    );
    for (const height of [900, 768, 640]) {
      await page.setViewportSize({ width: 1920, height });
      const metrics = await page
        .getByLabel('Current network metrics')
        .boundingBox();
      const legend = await page.getByLabel('Globe legend').boundingBox();
      expect(metrics && legend).toBeTruthy();
      expect(
        metrics!.y + metrics!.height <= legend!.y ||
          legend!.y + legend!.height <= metrics!.y,
        `height ${height}: metrics/legend ${JSON.stringify({ metrics, legend })}`
      ).toBe(true);
      expect(
        await page
          .locator('.overview-page')
          .evaluate((node) => node.scrollHeight > node.clientHeight),
        `height ${height}: short desktop remains scrollable`
      ).toBe(true);
      const shortPoiBox = await pois.boundingBox();
      for (const panel of await graphs.all()) {
        const box = await panel.boundingBox();
        expect(
          box && shortPoiBox && box.y + box.height <= shortPoiBox.y
        ).toBeTruthy();
        expect(box && box.width >= 200).toBeTruthy();
      }
      expect(
        await pois.evaluate((node) => node.scrollHeight <= node.clientHeight),
        `height ${height}: five POIs remain unclipped`
      ).toBe(true);
    }
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
