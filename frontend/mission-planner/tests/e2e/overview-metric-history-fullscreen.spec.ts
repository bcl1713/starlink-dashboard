import { writeFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

const metrics = [
  'starlink_network_latency_ms_current',
  'starlink_network_throughput_down_mbps_current',
  'starlink_network_throughput_up_mbps_current',
  'starlink_network_packet_loss_percent',
  'starlink_dish_obstruction_percent',
];
function representativeBundle(end: number, windowSeconds = 1800) {
  const times = Array.from(
    { length: windowSeconds / 30 + 1 },
    (_, sample) => end - windowSeconds + sample * 30
  );
  return {
    window_seconds: windowSeconds,
    start_timestamp_seconds: end - windowSeconds,
    end_timestamp_seconds: end,
    step_seconds: 30,
    series: Object.fromEntries(
      metrics.map((metric, index) => [
        metric,
        times.map((time, sample) => [
          time,
          10 + index * 8 + ((sample * (index + 3)) % 13),
        ]),
      ])
    ),
    rolling_5m: Object.fromEntries(
      metrics.map((metric, index) => [
        metric,
        {
          state: 'available',
          min: times.map((time, sample) => [
            time,
            7 + index * 8 + (sample % 7),
          ]),
          avg: times.map((time, sample) => [
            time,
            11 + index * 8 + (sample % 7),
          ]),
          max: times.map((time, sample) => [
            time,
            15 + index * 8 + (sample % 7),
          ]),
        },
      ])
    ),
  };
}

test.describe('Overview metric history', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });
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
    let selectedWindowSeconds = 1800;
    let fulfilledHistory = 0;
    await page.route('**/api/overview-history', async (route) => {
      await route.fulfill({
        json: representativeBundle(
          Math.floor(Date.now() / 1000),
          selectedWindowSeconds
        ),
      });
      fulfilledHistory++;
    });
    await page.route('**/api/overview-history/settings', (route) => {
      if (route.request().method() === 'PUT')
        selectedWindowSeconds = (
          route.request().postDataJSON() as { window_seconds: number }
        ).window_seconds;
      return route.fulfill({ json: { window_seconds: selectedWindowSeconds } });
    });
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
    await expect.poll(() => fulfilledHistory).toBeGreaterThan(0);
    await expect(graphs.getByRole('status')).toHaveText(
      Array(5).fill('History available')
    );
    const paintedRanges = async () =>
      graphs.locator('.uplot canvas').evaluateAll((canvases) =>
        canvases.map((node) => {
          const canvas = node as HTMLCanvasElement;
          const { width, height } = canvas;
          const pixels = canvas
            .getContext('2d')!
            .getImageData(0, 0, width, height).data;
          return [0.2, 0.5, 0.8].map((fraction) => {
            const center = Math.floor(width * fraction);
            for (let x = center - 5; x <= center + 5; x++)
              for (let y = 0; y < height; y++) {
                const offset = (y * width + x) * 4;
                if (
                  pixels[offset] < 170 &&
                  pixels[offset + 1] > 175 &&
                  pixels[offset + 2] > 185 &&
                  pixels[offset + 3] > 0
                )
                  return true;
              }
            return false;
          });
        })
      );
    await expect
      .poll(paintedRanges, { timeout: 10_000 })
      .toEqual(Array.from({ length: 5 }, () => [true, true, true]));
    await expect(pois.locator('tbody tr')).toHaveCount(5);
    await expect(pois.locator('tbody tr')).toHaveText(
      names.map((name) => new RegExp(name))
    );
    await expect(pois.getByTestId('upcoming-pois-body')).toHaveCSS(
      'height',
      '224px'
    );
    await page.getByRole('button', { name: /fullscreen/i }).click();
    await expect
      .poll(() =>
        page.evaluate(
          () => document.fullscreenElement === document.documentElement
        )
      )
      .toBe(true);
    await expect(page.getByRole('button', { name: /fullscreen/i })).toHaveCount(
      0
    );
    await pois.evaluate(async (node) => {
      await Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished.catch(() => undefined))
      );
    });
    const viewport = await page.evaluate(() => ({
      width: innerWidth,
      height: innerHeight,
      visualWidth: visualViewport?.width,
      visualHeight: visualViewport?.height,
      screenWidth: screen.width,
      screenHeight: screen.height,
      dpr: devicePixelRatio,
    }));
    expect(viewport).toEqual({
      width: 1920,
      height: 1080,
      visualWidth: 1920,
      visualHeight: 1080,
      screenWidth: 1920,
      screenHeight: 1080,
      dpr: 1,
    });
    const layout = async () =>
      page.evaluate(() => {
        const boxes = [...document.querySelectorAll('[data-metric-panel]')].map(
          (node) => node.getBoundingClientRect().toJSON()
        );
        const poi = document
          .querySelector('[aria-label="Upcoming POIs"]')!
          .getBoundingClientRect()
          .toJSON();
        const ticks = [
          ...document.querySelectorAll('.overview-metric-history__time-axis'),
        ].map((node) => ({
          height: node.getBoundingClientRect().height,
          lines: [...node.querySelectorAll('span')].map((span) => ({
            height: span.getBoundingClientRect().height,
            lineHeight: parseFloat(getComputedStyle(span).lineHeight),
          })),
        }));
        const stack = document.querySelector('.overview-bottom-overlays')!;
        return {
          boxes,
          panelScroll: [
            ...document.querySelectorAll('[data-metric-panel]'),
          ].map(
            (node) =>
              node.scrollHeight > node.clientHeight ||
              node.scrollWidth > node.clientWidth
          ),
          poi,
          neighbors: [
            '.overview-clock-panel',
            '[aria-label="Current network metrics"]',
            '[aria-label="Globe legend"]',
          ].map((selector) =>
            document.querySelector(selector)!.getBoundingClientRect().toJSON()
          ),
          ticks,
          stackBottom: stack.getBoundingClientRect().bottom,
          rowBottoms: [
            ...document.querySelectorAll(
              '[aria-label="Upcoming POIs"] tbody tr'
            ),
          ].map((row) => row.getBoundingClientRect().bottom),
          poiScroll:
            document.querySelector('[aria-label="Upcoming POIs"]')!
              .scrollHeight >
            document.querySelector('[aria-label="Upcoming POIs"]')!
              .clientHeight,
          poiSizes: (() => {
            const p = document.querySelector('[aria-label="Upcoming POIs"]')!;
            const b = p.querySelector('.upcoming-pois__body')!;
            return {
              scroll: p.scrollHeight,
              client: p.clientHeight,
              body: b.getBoundingClientRect().toJSON(),
            };
          })(),
          scroll:
            stack.scrollHeight > stack.clientHeight ||
            document.querySelector('.overview-page')!.scrollHeight >
              document.querySelector('.overview-page')!.clientHeight,
        };
      });
    const assertLayout = (state: Awaited<ReturnType<typeof layout>>) => {
      expect(state.boxes).toHaveLength(5);
      expect(state.panelScroll).toEqual(Array(5).fill(false));
      for (const box of [...state.boxes, state.poi])
        for (const neighbor of state.neighbors)
          expect(
            box.right <= neighbor.left ||
              neighbor.right <= box.left ||
              box.bottom <= neighbor.top ||
              neighbor.bottom <= box.top,
            `overlay collision: ${JSON.stringify({ box, neighbor })}`
          ).toBe(true);
      expect(state.poi.width).toBeGreaterThanOrEqual(320);
      expect(state.poi.width).toBeLessThanOrEqual(520);
      for (let i = 0; i < 5; i++) {
        const box = state.boxes[i];
        expect(Math.abs(box.x - state.poi.x)).toBeLessThan(2);
        expect(Math.abs(box.width - state.poi.width)).toBeLessThan(2);
        if (i)
          expect(
            box.y - (state.boxes[i - 1].y + state.boxes[i - 1].height)
          ).toBeGreaterThanOrEqual(0);
        if (i)
          expect(
            box.y - (state.boxes[i - 1].y + state.boxes[i - 1].height)
          ).toBeLessThanOrEqual(12);
      }
      expect(
        state.poi.y - (state.boxes[4].y + state.boxes[4].height)
      ).toBeGreaterThanOrEqual(0);
      expect(
        state.poi.y - (state.boxes[4].y + state.boxes[4].height)
      ).toBeLessThanOrEqual(12);
      expect(
        Math.abs(1080 - state.poi.bottom - 16),
        `POI bottom must be 1rem from viewport: ${JSON.stringify(state)}`
      ).toBeLessThanOrEqual(1);
      expect(Math.abs(1080 - state.stackBottom - 16)).toBeLessThanOrEqual(1);
      expect(state.scroll).toBe(false);
      expect(state.poiScroll, JSON.stringify(state)).toBe(false);
      expect(state.rowBottoms).toHaveLength(5);
      for (const bottom of state.rowBottoms)
        expect(bottom).toBeLessThanOrEqual(state.poi.bottom);
      for (const tick of state.ticks) {
        expect(tick.height).toBeLessThanOrEqual(18);
        for (const line of tick.lines)
          expect(line.height).toBeLessThanOrEqual(line.lineHeight + 1);
      }
    };
    const firstLayout = await layout();
    assertLayout(firstLayout);
    const firstUtcTick = await graphs
      .first()
      .locator('.overview-metric-history__time-axis span:first-child')
      .textContent();
    const image = await page.screenshot({
      path: testInfo.outputPath('overview-native-fullscreen-1920x1080.png'),
    });
    expect(image.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
    const raster = {
      width: image.readUInt32BE(16),
      height: image.readUInt32BE(20),
    };
    expect(raster).toEqual({ width: 1920, height: 1080 });
    await writeFile(
      testInfo.outputPath('overview-native-fullscreen-metrics.json'),
      JSON.stringify({ viewport, raster, layout: firstLayout }, null, 2)
    );
    await page.waitForTimeout(6_200);
    const laterLayout = await layout();
    assertLayout(laterLayout);
    await expect
      .poll(() =>
        graphs
          .first()
          .locator('.overview-metric-history__time-axis span:first-child')
          .textContent()
      )
      .not.toBe(firstUtcTick);
    expect(
      laterLayout.boxes.map(({ x, y, width, height }) => [x, y, width, height])
    ).toEqual(
      firstLayout.boxes.map(({ x, y, width, height }) => [x, y, width, height])
    );
    expect([
      laterLayout.poi.x,
      laterLayout.poi.y,
      laterLayout.poi.width,
      laterLayout.poi.height,
    ]).toEqual([
      firstLayout.poi.x,
      firstLayout.poi.y,
      firstLayout.poi.width,
      firstLayout.poi.height,
    ]);
    await expect(page.getByLabel('Current network metrics')).toBeVisible();
    await expect(page.getByLabel('Globe legend')).toBeVisible();
    await expect(page.locator('.overview-clock-panel')).toBeVisible();
    await expect(globeCanvas).toBeVisible();
    await expect(page.getByRole('navigation')).toHaveCount(0);
    const oldAxis = await graphs
      .first()
      .locator('.overview-metric-history__time-axis span:first-child')
      .textContent();
    await page.getByLabel('Aircraft history window').selectOption('900');
    await expect.poll(() => selectedWindowSeconds).toBe(900);
    await expect
      .poll(() =>
        graphs
          .first()
          .locator('.overview-metric-history__time-axis span:first-child')
          .textContent()
      )
      .not.toBe(oldAxis);
    assertLayout(await layout());
    await page.evaluate(() => document.exitFullscreen());
    await expect
      .poll(() => page.evaluate(() => document.fullscreenElement))
      .toBeNull();
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
});
