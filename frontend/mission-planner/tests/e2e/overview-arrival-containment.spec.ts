import { expect, test } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

test('contains long paired countdowns around the desktop panel breakpoint', async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1500, height: 1200 });
  for (const [endpoint, json] of [
    ['routes', { routes: [], total: 0 }],
    ['satellites', []],
    ['active-x-link', { satellite_id: null }],
    ['overview-clocks/settings', { clocks: [] }],
    ['overview-history/settings', { window_seconds: 300 }],
    [
      'overview-history',
      {
        series: {},
        window_seconds: 300,
        start_timestamp_seconds: Date.now() / 1000 - 300,
        end_timestamp_seconds: Date.now() / 1000,
        step_seconds: 1,
      },
    ],
    ['status', { timestamp: new Date().toISOString() }],
  ] as const)
    await page.route(`**/api/${endpoint}`, (route) => route.fulfill({ json }));
  await page.route('**/api/overview/upcoming-pois', (route) => {
    const now = Date.now();
    return route.fulfill({
      json: {
        state: 'available',
        flight_phase: 'in_flight',
        calculated_at: new Date(now).toISOString(),
        position_state: 'fresh',
        position_observed_at: new Date(now).toISOString(),
        current_route_progress: 10,
        pois: ['aar_start', 'arrival'].map((kind, index) => ({
          poi_id: `containment-${index}`,
          name: index ? 'RKSO' : 'AAR start',
          kind,
          latitude: 0,
          longitude: -50,
          projected_route_progress: 50 + index * 50,
          upcoming: true,
          map_retained: true,
          eta_type: 'estimated',
          estimated_arrival_time: new Date(now + 779 * 60_000).toISOString(),
        })),
      },
    });
  });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const texture = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === '/earth-day-hi.jpg' && response.ok(),
    { timeout: 20_000 }
  );
  await page.goto('/overview');
  await waitForGlobeVisualReady(page, texture);
  const panel = page.getByLabel('Departure and arrival');
  await expect(panel.locator('section')).toHaveCount(2);
  await expect(
    panel.locator('.overview-arrival__countdown').first()
  ).toHaveText('12 HR 59 MIN');
  const navigationHeight = await page
    .locator('.overview-page')
    .evaluate((node) => innerHeight - node.getBoundingClientRect().height);
  const results = [];
  for (const fullscreen of [false, true]) {
    for (const width of [1500, 1536, 1600, 1610, 1660, 1664, 1920]) {
      // The reported 1200px is the Overview container height, excluding navigation.
      await page.setViewportSize({
        width,
        height: 1200 + (fullscreen ? 0 : navigationHeight),
      });
      if (fullscreen) {
        await page
          .getByRole('button', { name: 'Enter fullscreen overview' })
          .click();
        await expect
          .poll(() => page.evaluate(() => !!document.fullscreenElement))
          .toBe(true);
      }
      await expect(panel.locator('.overview-arrival__sections')).toHaveCSS(
        'flex-direction',
        width <= 1660 ? 'column' : 'row'
      );
      await expect
        .poll(() =>
          page
            .locator('.overview-page')
            .evaluate((node) => node.getBoundingClientRect().height)
        )
        .toBe(1200);
      const geometry = await panel.evaluate((node) => {
        const box = node.getBoundingClientRect();
        const page = document
          .querySelector('.overview-page')!
          .getBoundingClientRect();
        return {
          width: box.width,
          availableWidth: node.parentElement!.getBoundingClientRect().width,
          pageHeight: page.height,
          center: box.x + box.width / 2,
          bottom: box.bottom,
          pageBottom: page.bottom,
          overflow: node.scrollWidth > node.clientWidth,
          contained: [...node.querySelectorAll('section, h2, p')].every(
            (child) => {
              const rect = child.getBoundingClientRect();
              return (
                rect.top >= box.top &&
                rect.left >= box.left &&
                rect.right <= box.right &&
                rect.bottom <= box.bottom &&
                child.scrollWidth <= child.clientWidth
              );
            }
          ),
        };
      });
      expect(geometry.pageHeight).toBe(1200);
      expect(geometry.availableWidth).toBe(width - 960);
      expect(geometry.overflow).toBe(false);
      expect(geometry.contained).toBe(true);
      expect(Math.abs(geometry.center - width / 2)).toBeLessThan(1);
      expect(Math.abs(geometry.bottom - geometry.pageBottom + 20)).toBeLessThan(
        1
      );
      results.push({ width, fullscreen, geometry });
      await page.screenshot({
        path: testInfo.outputPath(
          `countdowns-${width}-${fullscreen ? 'fullscreen' : 'ordinary'}.png`
        ),
      });
      if (fullscreen) {
        await page.evaluate(() => document.exitFullscreen());
        await expect
          .poll(() => page.evaluate(() => !!document.fullscreenElement))
          .toBe(false);
      }
    }
  }
  await testInfo.attach('containment', {
    body: JSON.stringify({
      sha: process.env.ACCEPTANCE_CANDIDATE_SHA ?? 'working-tree',
      source: 'whole-app Chromium with browser API fixtures',
      results,
    }),
    contentType: 'application/json',
  });
  expect(errors).toEqual([]);
});

test('contains long late departures with enlarged text on narrow screens', async ({
  page,
}, testInfo) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  const now = Date.parse('2026-10-01T12:00:00Z');
  await page.clock.install({ time: now });
  for (const [endpoint, json] of [
    ['routes', { routes: [], total: 0 }],
    ['satellites', []],
    ['active-x-link', { satellite_id: null }],
    ['overview-clocks/settings', { clocks: [] }],
    ['overview-history/settings', { window_seconds: 300 }],
    [
      'overview-history',
      {
        series: {},
        window_seconds: 300,
        start_timestamp_seconds: now / 1000 - 300,
        end_timestamp_seconds: now / 1000,
        step_seconds: 1,
      },
    ],
    ['status', { timestamp: new Date(now).toISOString() }],
    [
      'overview/upcoming-pois',
      {
        state: 'available',
        flight_phase: 'pre_departure',
        calculated_at: new Date(now).toISOString(),
        position_state: 'unavailable',
        position_observed_at: null,
        current_route_progress: null,
        scheduled_departure_time: '2026-09-30T23:01:00Z',
        pois: [
          {
            poi_id: 'departure',
            name: 'KADW',
            kind: 'departure',
            latitude: 38,
            longitude: -77,
            projected_route_progress: 0,
            upcoming: true,
            map_retained: true,
            eta_type: 'anticipated',
            estimated_arrival_time: null,
            eta_seconds: null,
          },
        ],
      },
    ],
  ] as const)
    await page.route(`**/api/${endpoint}`, (route) => route.fulfill({ json }));
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/overview');
  const panel = page.getByLabel('Departure and arrival');
  await expect(panel.locator('.overview-arrival__countdown')).toHaveText(
    '12 HR 59 MIN AGO'
  );
  const results = [];
  for (const rootSize of [16, 20, 24]) {
    await page.evaluate((size) => {
      document.documentElement.style.fontSize = `${size}px`;
    }, rootSize);
    for (const width of rootSize === 16 ? [320, 390, 844] : [390, 844]) {
      await page.setViewportSize({ width, height: 844 });
      await panel.scrollIntoViewIfNeeded();
      const geometry = await panel.evaluate((node) => {
        const box = node.getBoundingClientRect();
        const overview = document.querySelector('.overview-page')!;
        const countdown = node.querySelector('.overview-arrival__countdown')!;
        const range = document.createRange();
        range.selectNodeContents(countdown);
        return {
          centered: Math.abs(box.x + box.width / 2 - innerWidth / 2) < 1,
          panelOverflow: node.scrollWidth > node.clientWidth,
          pageOverflow: overview.scrollWidth > overview.clientWidth,
          textContained: [...range.getClientRects()].every(
            (rect) =>
              rect.left >= box.left &&
              rect.right <= box.right &&
              rect.top >= box.top &&
              rect.bottom <= box.bottom
          ),
          fontSize: getComputedStyle(countdown).fontSize,
          countdown: countdown.textContent,
        };
      });
      results.push({ width, rootSize, geometry });
      await page.screenshot({
        path: testInfo.outputPath(`late-${width}-root${rootSize}.png`),
      });
    }
  }
  await testInfo.attach('late-departure-containment', {
    body: JSON.stringify({
      sha: process.env.ACCEPTANCE_CANDIDATE_SHA ?? 'working-tree',
      results,
    }),
    contentType: 'application/json',
  });
  for (const { width, rootSize, geometry } of results) {
    expect(geometry, `${width}px / root ${rootSize}px`).toEqual({
      centered: true,
      panelOverflow: false,
      pageOverflow: false,
      textContained: true,
      fontSize: `${rootSize * 1.75}px`,
      countdown: '12 HR 59 MIN AGO',
    });
  }
  expect(errors).toEqual([]);
});
