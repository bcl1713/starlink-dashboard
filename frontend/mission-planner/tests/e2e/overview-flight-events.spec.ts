import { chromium, expect, test } from '@playwright/test';
import type { OverviewUpcomingPoisResponse } from '../../src/services/overview-upcoming-pois';

test('renders observed taxi and parking states on the provisioned CDP browser', async ({
  baseURL,
}, testInfo) => {
  const endpoint = process.env.ACCEPTANCE_CDP_URL;
  test.skip(!endpoint, 'Requires the provisioned acceptance CDP session');
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[0-9a-f]{40}$/);
  const browser = await chromium.connectOverCDP(endpoint!);
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  try {
    const page = await context.newPage();
    const now = Date.parse('2026-10-16T12:00:00Z');
    await page.clock.install({ time: now });
    let movement = 'taxi_out';
    let uncertain = false;
    await page.route('**/api/overview/upcoming-pois', async (route) => {
      const current = await page.evaluate(() => Date.now());
      const response: OverviewUpcomingPoisResponse = {
        state: 'available',
        calculated_at: new Date(current).toISOString(),
        flight_phase: movement === 'taxi_out' ? 'pre_departure' : 'in_flight',
        scheduled_departure_time: null,
        current_route_progress: 99,
        position_observed_at: new Date(current).toISOString(),
        position_state: 'fresh',
        pois: [],
        movement_state: movement,
        movement_uncertain: uncertain,
        movement_observed_at: new Date(current).toISOString(),
        on_blocks_at:
          movement === 'parked' ? new Date(current).toISOString() : null,
      };
      await route.fulfill({ json: response });
    });
    for (const [endpointName, json] of [
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
      await page.route(`**/api/${endpointName}`, (route) =>
        route.fulfill({ json })
      );
    await page.goto(`${baseURL}/overview`);
    const panel = page.getByLabel('Departure and arrival');
    for (const [state, label] of [
      ['taxi_out', 'TAXI OUT'],
      ['probable_landed_rollout', 'LANDED · INFERRED'],
      ['taxi_in', 'TAXI IN'],
      ['parked', 'PARKED'],
    ]) {
      movement = state;
      await page.clock.fastForward(5100);
      await expect(
        panel.getByRole('heading', { name: label, exact: true })
      ).toBeVisible();
      await expect(panel.locator('.overview-arrival__countdown')).toHaveCount(
        0
      );
      await page.screenshot({ path: testInfo.outputPath(`${state}.png`) });
    }
    uncertain = true;
    await page.clock.fastForward(5100);
    await expect(panel).toContainText('Movement state uncertain or stale');
    await testInfo.attach('source-and-revision', {
      body: JSON.stringify({
        candidate: process.env.ACCEPTANCE_CANDIDATE_SHA,
        source: 'synthetic API fixtures; not real flight calibration',
        viewport: [1920, 1080],
        browser: browser.version(),
      }),
      contentType: 'application/json',
    });
  } finally {
    await context.close();
    await browser.close();
  }
});
