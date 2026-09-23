import { expect, test } from '@playwright/test';
import { routeUrl } from './support/configured-origin';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

function routePattern(pathname: string): string {
  return routeUrl(test.info().project.use.baseURL, pathname);
}

test.describe('V2 mission activation to Overview', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test('activates a V2 leg before generated Overview POIs become available', async ({
    page,
  }) => {
    let activated = false;
    let legacyRequest = false;
    let overviewState: 'no_active_mission' | 'available' | 'route_unavailable' =
      'no_active_mission';

    const mission = {
      id: 'v2-parent',
      name: 'V2 Overview Mission',
      description: 'Stateful activation contract fixture',
      created_at: '2026-09-22T12:00:00.000Z',
      updated_at: '2026-09-22T12:00:00.000Z',
      metadata: {},
      legs: [
        {
          id: 'v2-leg',
          name: 'V2 Overview Leg',
          route_id: 'v2-route',
          transports: {
            initial_x_satellite_id: 'X-Atlantic',
          },
          is_active: false,
        },
      ],
    };
    const generatedOverviewPois = {
      state: 'available' as const,
      calculated_at: '2026-09-22T12:00:00.000Z',
      pois: [
        {
          poi_id: 'departure-kadw',
          name: 'KADW departure',
          kind: 'departure' as const,
          latitude: 20,
          longitude: -70,
          expected_arrival_time: '2026-09-22T11:30:00.000Z',
          eta_seconds: -1_800,
          estimated_arrival_time: '2026-09-22T11:30:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: false,
          map_retained: true,
        },
        {
          poi_id: 'arrival-rkso',
          name: 'RKSO arrival',
          kind: 'arrival' as const,
          latitude: 25,
          longitude: -65,
          expected_arrival_time: '2026-09-22T12:10:00.000Z',
          eta_seconds: 600,
          estimated_arrival_time: '2026-09-22T12:10:00.000Z',
          eta_type: 'anticipated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'x-band-transition',
          name: 'X-band handoff',
          kind: 'x_band_transition' as const,
          latitude: 30,
          longitude: -60,
          expected_arrival_time: '2026-09-22T12:20:00.000Z',
          eta_seconds: 1_200,
          estimated_arrival_time: '2026-09-22T12:20:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'ka-entry',
          name: 'Ka entry',
          kind: 'ka_coverage_entry' as const,
          latitude: 35,
          longitude: -55,
          expected_arrival_time: '2026-09-22T12:30:00.000Z',
          eta_seconds: 1_800,
          estimated_arrival_time: '2026-09-22T12:30:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'ka-transition',
          name: 'Ka transition',
          kind: 'ka_transition' as const,
          latitude: 40,
          longitude: -50,
          expected_arrival_time: '2026-09-22T12:40:00.000Z',
          eta_seconds: 2_400,
          estimated_arrival_time: '2026-09-22T12:40:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'aar-start',
          name: 'AAR start',
          kind: 'aar_start' as const,
          latitude: 45,
          longitude: -45,
          expected_arrival_time: '2026-09-22T13:00:00.000Z',
          eta_seconds: 3_600,
          estimated_arrival_time: '2026-09-22T13:00:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
      ],
    };

    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/api/missions')) {
        legacyRequest = true;
      }
    });

    await page.route(routePattern('/api/v2/missions/v2-parent'), async (route) => {
      await route.fulfill({
        json: {
          ...mission,
          legs: mission.legs.map((leg) => ({ ...leg, is_active: activated })),
        },
      });
    });
    await page.route(
      routePattern('/api/v2/missions/v2-parent/legs/v2-leg/activate'),
      async (route) => {
        expect(route.request().method()).toBe('POST');
        activated = true;
        overviewState = 'available';
        await route.fulfill({ status: 200, json: { leg_id: 'v2-leg' } });
      }
    );
    await page.route(routePattern('/api/overview/upcoming-pois'), async (route) => {
      await route.fulfill({
        json:
          overviewState === 'available' && activated
            ? generatedOverviewPois
            : {
                state: overviewState,
                calculated_at: '2026-09-22T12:00:00.000Z',
                pois: [],
              },
      });
    });
    await page.route(routePattern('/api/routes'), (route) =>
      route.fulfill({
        json: {
          routes: [
            {
              id: 'v2-route',
              name: 'V2 generated Overview route',
              point_count: 2,
              is_active: true,
            },
          ],
          total: 1,
        },
      })
    );
    await page.route(routePattern('/api/routes/v2-route'), (route) =>
      route.fulfill({
        json: {
          id: 'v2-route',
          name: 'V2 generated Overview route',
          points: [
            { latitude: 20, longitude: -70 },
            { latitude: 25, longitude: -65 },
          ],
        },
      })
    );
    await page.route(routePattern('/api/status'), (route) =>
      route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: { latitude: 20, longitude: -70, altitude: 35_000 },
          ground_entry_point: { latitude: 21, longitude: -69 },
        },
      })
    );

    await page.route(routePattern('/api/satellites'), (route) =>
      route.fulfill({ json: [] })
    );
    await page.route(routePattern('/api/active-x-link'), (route) =>
      route.fulfill({ json: { satellite_id: null } })
    );
    await page.route(routePattern('/api/overview-history'), (route) =>
      route.fulfill({
        json: {
          window_seconds: 1800,
          start_timestamp_seconds: 1_781_998_200,
          end_timestamp_seconds: 1_782_000_000,
          step_seconds: 1,
          series: {},
        },
      })
    );
    await page.route(routePattern('/api/overview-history/settings'), (route) =>
      route.fulfill({ json: { window_seconds: 1800 } })
    );
    await page.route(routePattern('/api/overview-clocks/settings'), (route) =>
      route.fulfill({ json: { clocks: [] } })
    );

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');
    await expect(page.getByLabel('Upcoming POIs')).toContainText(
      'No active mission leg.'
    );

    await page.goto('/missions/v2-parent');
    await page.getByRole('button', { name: 'Activate', exact: true }).click();
    await expect.poll(() => activated).toBe(true);

    await page.goto('/overview');
    await waitForGlobeVisualReady(page, earthTexture);
    const panel = page.getByLabel('Upcoming POIs');
    await expect(panel).toBeVisible();
    await expect(panel.getByRole('row')).toHaveCount(6);
    await expect(panel).toHaveCSS('overflow-y', 'hidden');
    await expect(panel.getByText('RKSO arrival', { exact: true })).toBeVisible();
    await expect(page.locator('[data-poi-label="departure-kadw"]')).toBeVisible();
    await expect(page.locator('[data-poi-label="arrival-rkso"]')).toBeVisible();
    expect(legacyRequest).toBe(false);

    overviewState = 'route_unavailable';
    await page.reload();
    await expect(page.getByLabel('Upcoming POIs')).toContainText(
      'Active mission leg is not bound to the active route.'
    );
    expect(legacyRequest).toBe(false);
  });
});
