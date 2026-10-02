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
  test('fits populated plots and the compact arrival panel together at 1920x1080', async ({
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
    let collapsePois = false;
    let fulfilledHistory = 0;
    let historyFails = false;
    let statusHangs = false;
    await page.route('**/api/overview-history', async (route) => {
      if (historyFails) {
        await route.fulfill({
          status: 503,
          json: { detail: 'Refresh unavailable' },
        });
        return;
      }
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
          state: collapsePois ? 'no_generated_pois' : 'available',
          calculated_at: new Date().toISOString(),
          flight_phase: 'in_flight',
          scheduled_departure_time: null,
          position_state: 'fresh',
          position_observed_at: new Date().toISOString(),
          pois: (collapsePois ? [] : names).map((name, index) => ({
            poi_id: `busy-${index}`,
            projected_route_progress: 10 + index * 20,
            flight_phase: 'in_flight',
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
      statusHangs
        ? new Promise(() => {})
        : route.fulfill({
            json: {
              timestamp: new Date(Date.now() - 1000).toISOString(),
              metric_availability: {
                latency_ms: true,
                throughput_down_mbps: true,
                throughput_up_mbps: true,
                packet_loss_percent: true,
                obstruction_percent: true,
              },
              network: {
                latency_ms: 42,
                throughput_down_mbps: 125.3,
                throughput_up_mbps: 25.1,
                packet_loss_percent: 0.5,
              },
              obstruction: { obstruction_percent: 15 },
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
    const pois = page.getByLabel('Departure and arrival');
    await expect(graphs.locator('.uplot')).toHaveCount(5);
    await expect.poll(() => fulfilledHistory).toBeGreaterThan(0);
    await expect(graphs.getByRole('status')).toHaveCount(0);
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
    await expect(pois.locator('.overview-arrival__section')).toHaveCount(2);
    await expect(pois).toContainText(names[0]);
    await expect(pois).toContainText(names.at(-1)!);
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
          .querySelector('[aria-label="Departure and arrival"]')!
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
        const stack = document.querySelector('.overview-metrics-overlays')!;
        return {
          boxes,
          contents: [...document.querySelectorAll('[data-metric-panel]')].map(
            (panel) =>
              [
                ...panel.querySelectorAll(
                  '.overview-metric-history__header, .overview-metric-history__latest, .overview-metric-history__age, .overview-metric-history__status, .overview-metric-history__chart, .overview-metric-history__time-axis'
                ),
              ]
                .filter(
                  (node) => !node.classList.contains('overview-visually-hidden')
                )
                .map((node) => ({
                  className: node.className,
                  text: node.textContent,
                  box: node.getBoundingClientRect().toJSON(),
                }))
          ),
          plotHeights: [
            ...document.querySelectorAll('.overview-metric-history__viewport'),
          ].map((node) => node.getBoundingClientRect().height),
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
            '[aria-label="Network history context"]',
            '[aria-label="Globe legend"]',
            '[aria-label="Planned satellite"]',
            '.overview-map-overlays',
          ].map((selector) =>
            document.querySelector(selector)!.getBoundingClientRect().toJSON()
          ),
          ticks,
          stackBottom: stack.getBoundingClientRect().bottom,
          rowBottoms: [
            ...document.querySelectorAll(
              '[aria-label="Departure and arrival"] .overview-arrival__section'
            ),
          ].map((row) => row.getBoundingClientRect().bottom),
          poiScroll:
            document.querySelector('[aria-label="Departure and arrival"]')!
              .scrollHeight >
            document.querySelector('[aria-label="Departure and arrival"]')!
              .clientHeight,
          poiSizes: (() => {
            const p = document.querySelector(
              '[aria-label="Departure and arrival"]'
            )!;
            const b = p.querySelector('.overview-arrival__sections') ?? p;
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
      expect(state.plotHeights.every((height) => height >= 48)).toBe(true);
      for (const [index, contents] of state.contents.entries()) {
        const parent = state.boxes[index];
        for (const { box } of contents) {
          expect(box.width).toBeGreaterThan(0);
          expect(box.height).toBeGreaterThan(0);
          expect(box.left).toBeGreaterThanOrEqual(parent.left);
          expect(box.right).toBeLessThanOrEqual(parent.right);
          expect(box.top).toBeGreaterThanOrEqual(parent.top);
          expect(box.bottom).toBeLessThanOrEqual(parent.bottom);
        }
        for (let first = 0; first < contents.length; first++)
          for (let second = first + 1; second < contents.length; second++) {
            const a = contents[first].box;
            const b = contents[second].box;
            expect(
              a.right <= b.left ||
                b.right <= a.left ||
                a.bottom <= b.top ||
                b.bottom <= a.top,
              `metric content overlap: ${JSON.stringify(contents)}`
            ).toBe(true);
          }
      }
      for (const box of [...state.boxes, state.poi])
        for (const neighbor of state.neighbors)
          expect(
            box.right <= neighbor.left ||
              neighbor.right <= box.left ||
              box.bottom <= neighbor.top ||
              neighbor.bottom <= box.top,
            `overlay collision: ${JSON.stringify({ box, neighbor })}`
          ).toBe(true);
      expect(state.poi.width).toBeGreaterThan(0);
      expect(state.poi.width).toBeLessThanOrEqual(1080);
      expect(Math.abs(state.poi.x + state.poi.width / 2 - 1020)).toBeLessThan(
        1
      );
      for (let i = 0; i < 5; i++) {
        const box = state.boxes[i];
        expect(box.right).toBeLessThanOrEqual(state.poi.left);
        expect(box.width).toBe(440);
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
        Math.abs(1080 - state.poi.bottom - 20),
        `POI bottom must be 20px from viewport: ${JSON.stringify(state)}`
      ).toBeLessThanOrEqual(1);
      expect(Math.abs(1080 - state.stackBottom - 20)).toBeLessThanOrEqual(1);
      expect(state.scroll).toBe(false);
      expect(state.poiScroll, JSON.stringify(state)).toBe(false);
      expect(state.rowBottoms).toHaveLength(2);
      for (const bottom of state.rowBottoms)
        expect(bottom).toBeLessThanOrEqual(state.poi.bottom);
    };
    const firstLayout = await layout();
    // Preserve visual evidence even when the fullscreen fit contract fails.
    await page.screenshot({
      path: testInfo.outputPath(
        'overview-fullscreen-fit-diagnostic-1920x1080.png'
      ),
    });
    await writeFile(
      testInfo.outputPath('overview-fullscreen-fit-diagnostic.json'),
      JSON.stringify(firstLayout, null, 2)
    );
    assertLayout(firstLayout);
    for (const [index, value] of [
      '42 ms',
      '125.3 Mbps',
      '25.1 Mbps',
      '0.5%',
      '15%',
    ].entries()) {
      await expect(
        graphs.nth(index).locator('.overview-metric-history__latest')
      ).toHaveText(value);
      await expect(
        graphs.nth(index).locator('.overview-metric-history__age')
      ).toContainText('Observed');
    }
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
    await expect(page.getByLabel('Network history context')).toBeVisible();
    await expect(page.getByLabel('Globe legend')).toBeVisible();
    await expect(page.locator('.overview-clock-panel')).toBeVisible();
    await expect(globeCanvas).toBeVisible();
    await expect(page.getByRole('navigation')).toHaveCount(0);
    const oldAxis = await graphs
      .first()
      .locator('.overview-metric-history__time-axis span:first-child')
      .textContent();
    await page.evaluate(() => document.exitFullscreen());
    await page
      .getByRole('link', { name: 'Configuration', exact: true })
      .click();
    await page.getByLabel('Overview history window').selectOption('900');
    await expect(page.getByLabel('Overview history window')).toHaveValue('900');
    await page.getByRole('link', { name: 'Overview', exact: true }).click();
    await page
      .getByRole('button', { name: 'Enter fullscreen overview' })
      .click();
    await expect
      .poll(() => page.evaluate(() => Boolean(document.fullscreenElement)))
      .toBe(true);
    await expect
      .poll(async () => (await graphs.first().boundingBox())?.width)
      .toBe(440);
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
    statusHangs = true;
    historyFails = true;
    await expect(graphs.getByRole('status')).toHaveCount(5, {
      timeout: 12_000,
    });
    for (const panel of await graphs.all()) {
      await expect(panel.getByRole('status')).toHaveText(
        'Last-known history; refresh unavailable'
      );
      // History failure can precede expiry of the ten-second status sample.
      await expect(
        panel.locator('.overview-metric-history__latest')
      ).toHaveText('Unavailable', { timeout: 15_000 });
      await expect(
        panel.locator('.overview-metric-history__age')
      ).toContainText('Last observed');
    }
    const staleLayout = await layout();
    assertLayout(staleLayout);
    await writeFile(
      testInfo.outputPath('overview-native-fullscreen-stale.json'),
      JSON.stringify(staleLayout, null, 2)
    );
    await page.screenshot({
      path: testInfo.outputPath('overview-native-fullscreen-stale.png'),
    });
    historyFails = false;
    await expect(graphs.getByRole('status')).toHaveCount(0, {
      timeout: 12_000,
    });
    await expect(
      page.getByText('History refresh unavailable', { exact: true })
    ).toHaveCount(0);
    assertLayout(await layout());
    // The compact header contracts when its exception clears. Isolate POI
    // collapse from that intended header change when comparing card positions.
    const recoveredLayout = await layout();
    collapsePois = true;
    await expect(pois.locator('.overview-arrival__section')).toHaveCount(0, {
      timeout: 12_000,
    });
    await pois.evaluate(async (node) => {
      await Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished.catch(() => undefined))
      );
    });
    const collapsed = await layout();
    expect(collapsed.poi.height).toBeLessThan(firstLayout.poi.height - 40);
    expect(
      Math.abs(collapsed.boxes[0].top - recoveredLayout.boxes[0].top)
    ).toBeLessThanOrEqual(1);
    expect(Math.abs(1080 - collapsed.poi.bottom - 20)).toBeLessThanOrEqual(1);
    expect(collapsed.boxes[4].right).toBeLessThanOrEqual(collapsed.poi.left);
    expect(collapsed.panelScroll).toEqual(Array(5).fill(false));
    expect(collapsed.poiScroll).toBe(false);
    await writeFile(
      testInfo.outputPath('overview-native-fullscreen-collapsed.json'),
      JSON.stringify({ layout: collapsed }, null, 2)
    );
    collapsePois = false;
    await expect(pois.locator('.overview-arrival__section')).toHaveCount(2, {
      timeout: 12_000,
    });
    await pois.evaluate(async (node) => {
      await Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished.catch(() => undefined))
      );
    });
    await page.evaluate(() => document.exitFullscreen());
    await expect
      .poll(() => page.evaluate(() => document.fullscreenElement))
      .toBeNull();
    // The desktop frame reserves navigation space and still fits ordinary 1080p.
    await expect
      .poll(() =>
        page
          .locator('.overview-page')
          .evaluate((node) => node.scrollHeight > node.clientHeight)
      )
      .toBe(false);
    await graphs.last().scrollIntoViewIfNeeded();
    await expect(graphs.last()).toBeInViewport();
    await pois.scrollIntoViewIfNeeded();
    await expect(pois).toBeInViewport();
    await expect(page.getByRole('button', { name: /fullscreen/i })).toHaveCount(
      1
    );
    await page.screenshot({
      path: testInfo.outputPath('overview-history-busy-1920x1080.png'),
      animations: 'disabled',
    });
    const poiSizing = await pois.evaluate((node) => ({
      scroll: node.scrollHeight,
      client: node.clientHeight,
      rows: [...node.querySelectorAll('.overview-arrival__section')].map(
        (row) => ({
          bottom: row.getBoundingClientRect().bottom,
          panelBottom: node.getBoundingClientRect().bottom,
        })
      ),
    }));
    expect(poiSizing.scroll, JSON.stringify(poiSizing)).toBeLessThanOrEqual(
      poiSizing.client
    );
    for (const height of [900, 768, 640]) {
      await page.setViewportSize({ width: 1920, height });
      const metrics = await page
        .getByLabel('Network history context')
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

for (const height of [961, 1024]) {
  test.describe(`Overview near-breakpoint native fullscreen ${height}`, () => {
    test.use({
      viewport: { width: 1920, height },
      screen: { width: 1920, height },
    });
    test('keeps populated charts and POIs clear of clocks and unclipped', async ({
      page,
    }, testInfo) => {
      const now = Date.now();
      await page.route('**/api/overview-history', (route) =>
        route.fulfill({
          json: representativeBundle(Math.floor(Date.now() / 1000)),
        })
      );
      await page.route('**/api/overview-history/settings', (route) =>
        route.fulfill({ json: { window_seconds: 1800 } })
      );
      await page.route('**/api/overview/upcoming-pois', (route) =>
        route.fulfill({
          json: {
            state: 'available',
            calculated_at: new Date(now).toISOString(),
            flight_phase: 'in_flight',
            scheduled_departure_time: null,
            position_state: 'fresh',
            position_observed_at: new Date(now).toISOString(),
            pois: Array.from({ length: 5 }, (_, index) => ({
              poi_id: `near-${index}`,
              projected_route_progress: 10 + index * 20,
              flight_phase: 'in_flight',
              name: `Waypoint ${index}`,
              kind: index === 4 ? 'arrival' : 'x_band_transition',
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
      await page.goto('/overview', { waitUntil: 'commit' });
      const graphs = page
        .getByLabel('Overview metric history')
        .locator('[data-metric-panel]');
      const pois = page.getByLabel('Departure and arrival');
      await expect(graphs.locator('.uplot')).toHaveCount(5);
      await expect(graphs.getByRole('status')).toHaveCount(0);
      await expect(pois.locator('.overview-arrival__section')).toHaveCount(2);
      await page.getByRole('button', { name: /fullscreen/i }).click();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.fullscreenElement === document.documentElement
          )
        )
        .toBe(true);
      await expect(
        page.getByRole('navigation', { name: 'Primary navigation' })
      ).toHaveCount(0);
      await pois.evaluate(async (node) => {
        await Promise.all(
          node
            .getAnimations({ subtree: true })
            .map((animation) => animation.finished.catch(() => undefined))
        );
      });
      const geometry = await page.evaluate(() => {
        const rect = (selector: string) =>
          document.querySelector(selector)!.getBoundingClientRect().toJSON();
        const panels = [...document.querySelectorAll('[data-metric-panel]')];
        const poi = document.querySelector(
          '[aria-label="Departure and arrival"]'
        )!;
        const page = document.querySelector('.overview-page')!;
        return {
          viewport: {
            width: innerWidth,
            height: innerHeight,
            visualHeight: visualViewport?.height,
            screenHeight: screen.height,
          },
          boxes: panels.map((node) => node.getBoundingClientRect().toJSON()),
          panelScroll: panels.map(
            (node) => node.scrollHeight > node.clientHeight
          ),
          poi: poi.getBoundingClientRect().toJSON(),
          poiScroll: poi.scrollHeight > poi.clientHeight,
          rows: [...poi.querySelectorAll('.overview-arrival__section')].map(
            (node) => node.getBoundingClientRect().toJSON()
          ),
          clocks: rect('.overview-clock-panel'),
          pageScroll: page.scrollHeight > page.clientHeight,
        };
      });
      await writeFile(
        testInfo.outputPath(`near-${height}.json`),
        JSON.stringify(geometry, null, 2)
      );
      await page.screenshot({
        path: testInfo.outputPath(`near-${height}.png`),
      });
      expect(geometry.viewport).toEqual({
        width: 1920,
        height,
        visualHeight: height,
        screenHeight: height,
      });
      expect(geometry.boxes).toHaveLength(5);
      expect(geometry.panelScroll).toEqual(Array(5).fill(false));
      expect(geometry.poiScroll).toBe(false);
      expect(geometry.rows).toHaveLength(2);
      for (const row of geometry.rows)
        expect(row.bottom).toBeLessThanOrEqual(geometry.poi.bottom);
      for (const box of geometry.boxes)
        expect(
          box.bottom <= geometry.clocks.top ||
            box.top >= geometry.clocks.bottom ||
            box.right <= geometry.clocks.left ||
            box.left >= geometry.clocks.right,
          `chart/clock overlap: ${JSON.stringify(geometry)}`
        ).toBe(true);
      expect(
        geometry.pageScroll,
        `height ${height}: composition fit boundary`
      ).toBe(height < 1012);
      if (height >= 1012) {
        for (const box of geometry.boxes) {
          expect(box.width).toBe(440);
          expect(box.bottom).toBeLessThanOrEqual(height - 20);
        }
      }
    });
  });
}
