import { expect, test } from '@playwright/test';
import type {
  OverviewUpcomingPoi,
  OverviewUpcomingPoisResponse,
} from '../../src/services/overview-upcoming-pois';

test.use({ viewport: { width: 1920, height: 1080 }, video: 'on' });

test('shows departure, arrival, stale, missing and landed states without losing map context', async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  const now = Date.parse('2026-10-01T12:00:00Z');
  await page.clock.install({ time: now });
  let phase: OverviewUpcomingPoisResponse['flight_phase'] = 'in_flight';
  let positionState: OverviewUpcomingPoisResponse['position_state'] = 'fresh';
  let destinationOnly = false;
  let missingEstimate = false;
  let fail = false;
  let departure = '2026-10-01T13:39:00Z';
  let missingDestination = false;
  const events: OverviewUpcomingPoi[] = [
    {
      poi_id: 'departure',
      name: 'KADW',
      kind: 'departure',
      projected_route_progress: 0,
      flight_phase: 'in_flight',
      latitude: 0,
      longitude: -60,
      expected_arrival_time: null,
      estimated_arrival_time: null,
      eta_seconds: null,
      eta_type: 'estimated',
      upcoming: false,
      map_retained: true,
    },
    {
      poi_id: 'event',
      name: 'A very long intermediate mission event with a deliberately wrapped operational name',
      kind: 'aar_start',
      projected_route_progress: 20,
      flight_phase: 'in_flight',
      latitude: 0,
      longitude: -50,
      expected_arrival_time: null,
      estimated_arrival_time: '2026-10-01T12:39:00Z',
      eta_seconds: 2340,
      eta_type: 'estimated',
      upcoming: true,
      map_retained: true,
    },
    {
      poi_id: 'destination',
      name: 'RKSO',
      kind: 'arrival',
      projected_route_progress: 100,
      flight_phase: 'in_flight',
      latitude: 0,
      longitude: -40,
      expected_arrival_time: '2026-10-01T15:00:00Z',
      estimated_arrival_time: '2026-10-01T13:39:00Z',
      eta_seconds: 5940,
      eta_type: 'estimated',
      upcoming: true,
      map_retained: true,
    },
  ];
  await page.route('**/api/overview/upcoming-pois', async (route) => {
    if (fail)
      return route.fulfill({ status: 503, json: { detail: 'Unavailable' } });
    const current = await page.evaluate(() => Date.now());
    const response: OverviewUpcomingPoisResponse = {
      state: 'available',
      calculated_at: new Date(current).toISOString(),
      flight_phase: phase,
      scheduled_departure_time: departure,
      current_route_progress: positionState === 'unavailable' ? null : 10,
      position_state: positionState,
      position_observed_at:
        positionState === 'unavailable'
          ? null
          : new Date(
              current - (positionState === 'stale' ? 20_000 : 0)
            ).toISOString(),
      pois: events
        .filter((p) => !missingDestination || p.kind !== 'arrival')
        .map((p) => ({
          ...p,
          upcoming:
            phase === 'post_arrival'
              ? false
              : p.kind === 'aar_start'
                ? !destinationOnly
                : p.kind === 'arrival',
          estimated_arrival_time:
            missingEstimate || positionState !== 'fresh'
              ? null
              : p.estimated_arrival_time,
        })),
    };
    await route.fulfill({ json: response });
  });
  for (const [endpoint, json] of [
    ['routes', { routes: [], total: 0 }],
    ['satellites', []],
    ['active-x-link', { satellite_id: null }],
    ['overview-clocks/settings', { clocks: [] }],
    ['overview-history/settings', { window_seconds: 300 }],
    [
      'overview-history',
      {
        window_seconds: 300,
        start_timestamp_seconds: now / 1000 - 300,
        end_timestamp_seconds: now / 1000,
        step_seconds: 1,
        series: {},
      },
    ],
    ['status', { timestamp: new Date(now).toISOString() }],
  ] as const)
    await page.route(`**/api/${endpoint}`, (route) => route.fulfill({ json }));
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/overview');
  const panel = page.getByLabel('Departure and arrival');
  await expect(panel.locator('section')).toHaveCount(2);
  await expect(panel).toContainText('39 MIN');
  await expect(panel).toContainText('1 HR 39 MIN');
  await panel.scrollIntoViewIfNeeded();
  await page.screenshot({
    path: testInfo.outputPath('arrival-intermediate-ordinary.png'),
  });
  await page.getByRole('button', { name: 'Enter fullscreen overview' }).click();
  await expect
    .poll(() => page.evaluate(() => !!document.fullscreenElement))
    .toBe(true);
  await expect(panel).toBeInViewport();
  const pairedBox = await panel.boundingBox();
  expect(Math.abs(pairedBox!.x + pairedBox!.width / 2 - 1020)).toBeLessThan(1);
  expect(Math.abs(pairedBox!.y + pairedBox!.height - 1060)).toBeLessThan(1);
  await expect(panel.locator('section').last()).toHaveCSS(
    'border-left-width',
    '1px'
  );
  for (const text of await panel.locator('h2, p').all())
    await expect(text).toHaveCSS('text-align', 'center');
  expect(
    await panel.locator('section').evaluateAll((sections) =>
      sections.every((section) => {
        const countdown = section.querySelector(
          '.overview-arrival__countdown'
        )!;
        return (
          section.scrollWidth <= section.clientWidth &&
          countdown.getBoundingClientRect().height <=
            parseFloat(getComputedStyle(countdown).lineHeight) + 1
        );
      })
    )
  ).toBe(true);
  await page.screenshot({
    path: testInfo.outputPath('arrival-intermediate-fullscreen.png'),
  });
  const metadata = await page.evaluate(() => ({
    viewport: [innerWidth, innerHeight],
    dpr: devicePixelRatio,
    renderer: (() => {
      const gl = document
        .querySelector('.overview-globe canvas, canvas')
        ?.getContext('webgl2');
      if (!gl) return null;
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null;
    })(),
  }));
  await testInfo.attach('browser-context', {
    body: JSON.stringify(
      {
        ...metadata,
        sha: process.env.ACCEPTANCE_CANDIDATE_SHA ?? 'working-tree',
        source: 'browser API fixtures',
        browser: page.context().browser()?.version(),
        hardwareAcceptance: false,
        operatorReadability: 'pending',
      },
      null,
      2
    ),
    contentType: 'application/json',
  });
  const refresh = async () => {
    await page.clock.fastForward(5_100);
    await expect(panel).toBeVisible();
  };
  destinationOnly = true;
  await refresh();
  await expect(panel.locator('section')).toHaveCount(1);
  await expect(
    panel.getByRole('heading', { name: 'LANDING · RKSO' })
  ).toBeVisible();
  const singleBox = await panel.boundingBox();
  expect(singleBox!.width).toBeLessThan(pairedBox!.width);
  expect(Math.abs(singleBox!.x + singleBox!.width / 2 - 1020)).toBeLessThan(1);
  await expect(panel.locator('section')).toHaveCSS('border-left-width', '0px');
  await page.screenshot({
    path: testInfo.outputPath('arrival-destination-only.png'),
  });
  positionState = 'stale';
  await refresh();
  await expect(panel).toContainText('Position stale');
  await expect(panel.locator('time')).toHaveCount(0);
  await expect(page.getByLabel('Map POIs')).toContainText(events[1].name);
  await page.screenshot({ path: testInfo.outputPath('arrival-stale.png') });
  positionState = 'unavailable';
  await refresh();
  await expect(panel).toContainText('Position unavailable');
  await expect(panel).toContainText('Next POI unavailable');
  positionState = 'fresh';
  missingEstimate = true;
  await refresh();
  await expect(panel.locator('time')).toHaveCount(0);
  await expect(panel).toContainText('ETA unavailable');
  await page.screenshot({
    path: testInfo.outputPath('arrival-missing-eta.png'),
  });
  missingDestination = true;
  await refresh();
  await expect(panel).toContainText('Destination unavailable');
  missingDestination = false;
  missingEstimate = false;
  phase = 'pre_departure';
  await refresh();
  await expect(
    panel.getByRole('heading', { name: 'SCHEDULED DEPARTURE · KADW' })
  ).toBeVisible();
  await expect(panel).toContainText('1 HR');
  await expect(panel.getByRole('heading', { name: /LANDING/ })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('departure-early.png') });
  departure = '2026-10-01T11:48:00Z';
  await refresh();
  await expect(panel).toContainText('12 MIN AGO');
  await expect(panel.locator('.overview-arrival__countdown--late')).toHaveCSS(
    'color',
    'rgb(255, 133, 133)'
  );
  await page.screenshot({ path: testInfo.outputPath('departure-late.png') });
  fail = true;
  await refresh();
  await expect(panel).toContainText('Arrival refresh unavailable');
  await expect(panel.locator('time')).toHaveCount(0);
  fail = false;
  phase = 'post_arrival';
  await refresh();
  await expect(
    panel.getByRole('heading', { name: 'LANDED · RKSO' })
  ).toBeVisible();
  await expect(panel.locator('.overview-arrival__countdown')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('arrival-landed.png') });
  await page.evaluate(() => document.exitFullscreen());
  phase = 'in_flight';
  destinationOnly = false;
  await refresh();
  for (const viewport of [
    { width: 390, height: 844 },
    { width: 844, height: 390 },
    { width: 360, height: 800 },
  ]) {
    await page.setViewportSize(viewport);
    await panel.scrollIntoViewIfNeeded();
    await expect(panel).toBeInViewport();
    expect(
      await page
        .locator('.overview-page')
        .evaluate((n) => n.scrollWidth > n.clientWidth)
    ).toBe(false);
    await page.screenshot({
      path: testInfo.outputPath(
        `arrival-${viewport.width}x${viewport.height}.png`
      ),
    });
  }
  expect(errors).toEqual([]);
});
