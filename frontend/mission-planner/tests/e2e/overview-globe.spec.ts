import { expect, test } from '@playwright/test';
import { waitForGlobeVisualReady } from './support/globe-visual-ready';

test.describe('Globe overview', () => {
  test.describe.configure({ mode: 'serial' });
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        json: [],
      });
    });
    await page.route('**/api/active-x-link', async (route) => {
      await route.fulfill({
        json: {
          satellite_id: null,
        },
      });
    });
    await page.route('**/api/overview-history', async (route) => {
      await route.fulfill({
        json: {
          window_seconds: 1800,
          start_timestamp_seconds: 1_781_998_200,
          end_timestamp_seconds: 1_782_000_000,
          step_seconds: 1,
          series: {},
        },
      });
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      await route.fulfill({
        json: {
          window_seconds: 1800,
        },
      });
    });
    await page.route('**/api/overview-clocks/settings', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          clocks: [
            { label: 'Zulu / UTC', time_zone: 'UTC' },
            { label: 'Washington, DC', time_zone: 'America/New_York' },
            { label: 'Omaha, NE', time_zone: 'America/Chicago' },
            { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
          ],
        }),
      });
    });
  });
  test('hides primary navigation during native overview fullscreen', async ({
    page,
  }) => {
    await page.goto('/overview');
    const fullscreenControl = page.getByRole('button', {
      name: 'Enter fullscreen overview',
    });

    await expect(fullscreenControl).toBeVisible();
    await expect(fullscreenControl).toBeEnabled();

    const fullscreenChange = page.evaluate(
      () =>
        new Promise<void>((resolve) => {
          document.addEventListener('fullscreenchange', () => resolve(), {
            once: true,
          });
        })
    );

    await fullscreenControl.click();
    await fullscreenChange;
    expect(
      await page.evaluate(
        () => document.fullscreenElement === document.documentElement
      )
    ).toBe(true);

    await expect(
      page.getByRole('navigation', {
        name: 'Primary navigation',
      })
    ).toHaveCount(0);
  });
  test('offers native fullscreen for the overview', async ({ page }) => {
    await page.goto('/overview');
    await expect(
      page.getByRole('button', {
        name: 'Enter fullscreen overview',
      })
    ).toBeVisible();
  });
  test('renders four operational clocks from saved settings', async ({
    page,
  }) => {
    await page.goto('/overview');
    await expect(
      page.getByRole('region', { name: 'Operational clocks' })
    ).toBeVisible();
    await expect(
      page.getByRole('region', { name: /zulu \/ utc operational clock/i })
    ).toBeVisible();
    await expect(
      page.getByRole('region', {
        name: /washington, dc operational clock/i,
      })
    ).toBeVisible();
    await expect(
      page.getByRole('region', { name: /omaha, ne operational clock/i })
    ).toBeVisible();
    await expect(
      page.getByRole('region', { name: /tokyo, jp operational clock/i })
    ).toBeVisible();
  });

  test('renders an active anti-meridian route from same-origin API data', async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.addInitScript(`
      const RealDate = Date;
      const fixedTime = '2026-06-21T12:00:00.000Z';

      class FixedDate extends RealDate {
        constructor(...args) {
          super(args.length === 0 ? fixedTime : args[0]);
        }

        static now() {
          return new RealDate(fixedTime).getTime();
        }
      }

      window.Date = FixedDate;
    `);
    const routeRequests: string[] = [];
    const statusRequests: string[] = [];

    await page.route('**/api/routes', async (route) => {
      routeRequests.push(route.request().url());

      await route.fulfill({
        json: {
          routes: [
            {
              id: 'active-anti-meridian',
              name: 'Anti-meridian validation route',
              point_count: 2,
              is_active: true,
            },
          ],
          total: 1,
        },
      });
    });

    await page.route('**/api/routes/active-anti-meridian', async (route) => {
      routeRequests.push(route.request().url());

      await route.fulfill({
        json: {
          id: 'active-anti-meridian',
          name: 'Anti-meridian validation route',
          points: [
            { latitude: 0, longitude: 179 },
            { latitude: 0, longitude: -179 },
          ],
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      statusRequests.push(route.request().url());

      await route.fulfill({
        json: {
          timestamp: '2026-06-21T12:00:00.000Z',
          position: {
            latitude: 12,
            longitude: 160,
            altitude: 35_000,
          },
          network: {
            latency_ms: 42.5,
            throughput_down_mbps: 125.3,
            throughput_up_mbps: 25.1,
            packet_loss_percent: 0.5,
          },
          environmental: {
            signal_quality_percent: 85,
          },
          ground_entry_point: {
            latitude: 41.2565,
            longitude: -95.9345,
          },
        },
      });
    });

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        json: [
          {
            satellite_id: 'X-Prime',
            transport: 'X',
            longitude: 160,
          },
        ],
      });
    });
    await page.route('**/api/active-x-link', async (route) => {
      await route.fulfill({
        json: {
          satellite_id: 'X-Prime',
          state: 'normal',
        },
      });
    });

    await page.goto('/overview');

    const metricsPanel = page.getByLabel('Current network metrics');

    await expect(metricsPanel).toBeVisible();
    await expect(
      metricsPanel.getByText('Live telemetry', { exact: true })
    ).toBeVisible();
    await expect(metricsPanel).toContainText('Updated 2026-06-21 12:00:00 UTC');
    await expect(metricsPanel).toContainText(/Latency\s*42\.5 ms/);
    await expect(metricsPanel).toContainText(/Downlink\s*125\.3 Mbps/);
    await expect(metricsPanel).toContainText(/Uplink\s*25\.1 Mbps/);
    await expect(metricsPanel).toContainText(/Packet loss\s*0\.5%/);
    await expect(metricsPanel).toContainText(/Signal quality\s*85%/);

    await expect.poll(() => statusRequests.length).toBeGreaterThanOrEqual(1);

    expect(statusRequests[0]).toMatch(/\/api\/status$/);

    await expect(page.getByLabel('Globe legend')).toBeVisible();
    const canvas = await waitForGlobeVisualReady(page, earthTexture);
    await expect(page.getByText('GEP', { exact: true })).toBeVisible();
    await expect(
      page.getByText('Anti-meridian validation route', { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText('Selected configured satellite X-Prime', { exact: true })
    ).toBeVisible();
    await expect(
      page.getByText(/Configured GEO estimate: azimuth .* elevation .*/, {
        exact: false,
      })
    ).toBeVisible();
    expect(await canvas.screenshot()).toMatchSnapshot(
      'overview-globe-ready.png',
      {
        maxDiffPixelRatio: 0.02,
      }
    );
    await expect.poll(() => routeRequests).toHaveLength(2);

    expect(routeRequests[0]).toMatch(/\/api\/routes$/);
    expect(routeRequests[1]).toMatch(/\/api\/routes\/active-anti-meridian$/);
  });

  test('renders a projectable configured X-band warning link', async ({
    page,
  }) => {
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [
            {
              id: 'warning-link-route',
              name: 'Warning link validation route',
              point_count: 2,
              is_active: true,
            },
          ],
          total: 1,
        },
      });
    });
    await page.route('**/api/routes/warning-link-route', async (route) => {
      await route.fulfill({
        json: {
          id: 'warning-link-route',
          name: 'Warning link validation route',
          points: [
            { latitude: 12, longitude: -90 },
            { latitude: 13, longitude: -89 },
          ],
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: '2026-06-21T12:00:00.000Z',
          position: { latitude: 12, longitude: -90, altitude: 35_000 },
          network: {
            latency_ms: 42.5,
            throughput_down_mbps: 125.3,
            throughput_up_mbps: 25.1,
            packet_loss_percent: 0.5,
          },
          environmental: { signal_quality_percent: 85 },
        },
      });
    });
    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        json: [{ satellite_id: 'X-Warning', transport: 'X', longitude: -90 }],
      });
    });
    await page.route('**/api/active-x-link', async (route) => {
      await route.fulfill({
        json: { satellite_id: 'X-Warning', state: 'warning' },
      });
    });

    await page.goto('/overview');

    await expect(
      page.getByText('Selected configured satellite X-Warning', { exact: true })
    ).toBeVisible();
  });

  test('refreshes status without overlapping requests', async ({ page }) => {
    await page.clock.install({ time: new Date('2026-06-21T12:00:00.000Z') });
    let statusRequestCount = 0;
    let inFlightRequests = 0;
    let maximumInFlightRequests = 0;
    let releaseSlowRefresh: (() => void) | undefined;

    const slowRefresh = new Promise<void>((resolve) => {
      releaseSlowRefresh = resolve;
    });

    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [
            {
              id: 'stale-status-route',
              name: 'Stale status validation route',
              point_count: 2,
              is_active: true,
            },
          ],
          total: 1,
        },
      });
    });

    await page.route('**/api/routes/stale-status-route', async (route) => {
      await route.fulfill({
        json: {
          id: 'stale-status-route',
          name: 'Stale status validation route',
          points: [
            { latitude: 0, longitude: 179 },
            { latitude: 0, longitude: -179 },
          ],
        },
      });
    });

    await page.route('**/api/status', async (route) => {
      statusRequestCount += 1;
      inFlightRequests += 1;
      maximumInFlightRequests = Math.max(
        maximumInFlightRequests,
        inFlightRequests
      );

      try {
        if (statusRequestCount > 1) {
          await slowRefresh;
        }

        await route.fulfill({
          json: {
            timestamp: new Date().toISOString(),
            position: {
              latitude: 0,
              longitude: 179,
            },
          },
        });
      } finally {
        inFlightRequests -= 1;
      }
    });

    await page.goto('/overview');
    await page.bringToFront();

    await expect.poll(() => statusRequestCount).toBe(1);

    await page.clock.fastForward(1_000);

    await expect.poll(() => statusRequestCount).toBeGreaterThanOrEqual(2);

    expect(maximumInFlightRequests).toBe(1);

    releaseSlowRefresh?.();
  });
  test('marks a previously fresh status sample as stale when refresh hangs', async ({
    page,
  }) => {
    const observedAt = '2026-06-21T12:00:00.000Z';
    let statusRequestCount = 0;

    await page.clock.install({
      time: new Date(observedAt),
    });

    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [
            {
              id: 'stale-status-route',
              name: 'Stale status validation route',
              point_count: 2,
              is_active: true,
            },
          ],
          total: 1,
        },
      });
    });

    await page.route('**/api/routes/stale-status-route', async (route) => {
      await route.fulfill({
        json: {
          id: 'stale-status-route',
          name: 'Stale status validation route',
          points: [
            { latitude: 0, longitude: 179 },
            { latitude: 0, longitude: -179 },
          ],
        },
      });
    });

    await page.route('**/api/status', async (route) => {
      statusRequestCount += 1;

      if (statusRequestCount === 1) {
        await route.fulfill({
          json: {
            timestamp: observedAt,
            position: {
              latitude: 0,
              longitude: 179,
            },
            ground_entry_point: null,
          },
        });

        return;
      }

      await new Promise(() => {});
    });

    await page.goto('/overview');
    const metricsPanel = page.getByLabel('Current network metrics');

    await expect(
      metricsPanel.getByText('Live telemetry', { exact: true })
    ).toBeVisible();

    await page.clock.fastForward(5_000);

    await expect(
      metricsPanel.getByText('Telemetry stale', { exact: true })
    ).toBeVisible();
    await expect(page.getByLabel('Globe legend')).toBeVisible();
    await expect(
      page.getByText('GEP unavailable', { exact: true })
    ).toBeVisible();
  });
  test('keeps aircraft and GEP context visible without an active route', async ({
    page,
  }) => {
    const observedAt = '2026-06-21T12:00:00.000Z';
    const satelliteRequests: string[] = [];
    const activeXLinkRequests: string[] = [];

    await page.addInitScript(`
      const RealDate = Date;
      const fixedTime = '${observedAt}';

      class FixedDate extends RealDate {
        constructor(...args) {
          super(args.length === 0 ? fixedTime : args[0]);
        }

        static now() {
          return new RealDate(fixedTime).getTime();
        }
      }

      window.Date = FixedDate;
    `);

    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });

    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: observedAt,
          position: {
            latitude: 0,
            longitude: -90,
          },
          ground_entry_point: {
            latitude: 41.2565,
            longitude: -95.9345,
          },
        },
      });
    });

    await page.route('**/api/satellites', async (route) => {
      satelliteRequests.push(route.request().url());

      await route.fulfill({
        json: [
          {
            satellite_id: 'X-Atlantic',
            transport: 'X',
            longitude: -60,
            slot: 'Atlantic',
            color: '#FF6B6B',
          },
          {
            satellite_id: 'X-Pacific',
            transport: 'X',
            longitude: 150,
            slot: 'Pacific',
            color: '#FF6B6B',
          },
        ],
      });
    });

    await page.route('**/api/active-x-link', async (route) => {
      activeXLinkRequests.push(route.request().url());
      await route.fulfill({
        json: {
          satellite_id: null,
        },
      });
    });

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');
    await expect(earthTexture).resolves.toBeTruthy();

    const globeLegend = page.getByLabel('Globe legend');

    await expect(
      page.getByText('No active route.', { exact: true })
    ).toBeVisible();
    await expect(globeLegend).toBeVisible();
    await expect.poll(() => satelliteRequests).toHaveLength(1);
    await expect.poll(() => activeXLinkRequests.length).toBeGreaterThan(0);
    expect(activeXLinkRequests).toEqual(
      expect.arrayContaining([expect.stringMatching(/\/api\/active-x-link$/)])
    );
    expect(satelliteRequests[0]).toMatch(/\/api\/satellites$/);
    await expect(
      globeLegend.getByText('Configured X-band satellites', { exact: true })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('2 configured satellites', { exact: true })
    ).toBeVisible();
    const activeConfiguredLinkRow = globeLegend.locator('li').filter({
      hasText:
        /^Active configured X-band link\s*No active configured X-band link$/,
    });
    await expect(activeConfiguredLinkRow.getByRole('strong')).toHaveText(
      'No active configured X-band link'
    );
    await expect(page.getByText('X-Atlantic', { exact: true })).toBeVisible();
    const satelliteLabelWhiteSpace = await page
      .getByText('X-Atlantic', { exact: true })
      .evaluate((label) => getComputedStyle(label).whiteSpace);
    expect(satelliteLabelWhiteSpace).toBe('nowrap');
    const overlayInteraction = await page
      .locator('.overview-top-overlays')
      .evaluate((topOverlay) => {
        const canvas = document.querySelector('canvas');
        const overlayBounds = topOverlay.getBoundingClientRect();
        const x = overlayBounds.left + overlayBounds.width / 2;
        const y = overlayBounds.top + overlayBounds.height / 2;
        const hitTarget = document.elementFromPoint(x, y);
        return {
          canvasIsHitTarget: hitTarget === canvas,
          canvasRect: canvas?.getBoundingClientRect().toJSON(),
          overlayPointerEvents: getComputedStyle(topOverlay).pointerEvents,
          x,
          y,
        };
      });
    expect(overlayInteraction.overlayPointerEvents).toBe('none');
    expect(overlayInteraction.canvasIsHitTarget).toBe(true);
    expect(overlayInteraction.canvasRect).not.toBeNull();
    const canvas = page.locator('canvas');
    const beforeDrag = await canvas.screenshot();
    await page.mouse.move(overlayInteraction.x, overlayInteraction.y);
    await page.mouse.down();
    await page.mouse.move(
      overlayInteraction.x + 180,
      overlayInteraction.y + 40,
      {
        steps: 12,
      }
    );
    await page.mouse.up();
    await expect
      .poll(async () => (await canvas.screenshot()).equals(beforeDrag))
      .toBe(false);
    await expect(
      globeLegend.getByText('Aircraft position', { exact: true })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('Live telemetry', { exact: true })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('Current/last-known', { exact: true })
    ).toBeVisible();
    await expect(page.getByText('GEP', { exact: true })).toBeVisible();
  });

  test('reports unavailable satellite configuration without a marker', async ({
    page,
  }) => {
    const observedAt = '2026-06-21T12:00:00.000Z';

    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });

    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: observedAt,
          position: {
            latitude: 0,
            longitude: -90,
          },
          ground_entry_point: null,
        },
      });
    });

    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        json: {
          detail: 'Satellite configuration unavailable',
        },
      });
    });

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');
    await expect(earthTexture).resolves.toBeTruthy();

    const globeLegend = page.getByLabel('Globe legend');

    await expect(
      globeLegend.getByText('Satellite configuration unavailable', {
        exact: true,
      })
    ).toBeVisible();

    await expect(
      globeLegend.getByText('X-Atlantic', { exact: true })
    ).toHaveCount(0);
  });
  test('hides invalid configured satellite records', async ({ page }) => {
    const observedAt = '2026-06-21T12:00:00.000Z';

    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });

    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: observedAt,
          position: {
            latitude: 0,
            longitude: -90,
          },
          ground_entry_point: null,
        },
      });
    });

    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        json: [
          {
            satellite_id: 'X-invalid',
            transport: 'X',
            longitude: 181,
            slot: 'Invalid slot',
            color: '#FF6B7B',
          },
        ],
      });
    });

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');
    await expect(earthTexture).resolves.toBeTruthy();

    const globeLegend = page.getByLabel('Globe legend');

    await expect(
      globeLegend.getByText('X-invalid', { exact: true })
    ).toHaveCount(0);
  });

  test('reports a whitespace-only configured satellite ID as invalid without a marker', async ({
    page,
  }) => {
    const observedAt = '2026-06-21T12:00:00.000Z';

    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });

    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: observedAt,
          position: {
            latitude: 0,
            longitude: -90,
          },
          ground_entry_point: null,
        },
      });
    });

    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        json: [
          {
            satellite_id: '   ',
            transport: 'X',
            longitude: -60,
          },
        ],
      });
    });

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');
    await expect(earthTexture).resolves.toBeTruthy();

    const globeLegend = page.getByLabel('Globe legend');

    const satelliteLegendEntry = globeLegend.locator('li').filter({
      hasText: 'Configured X-band satellites',
    });

    await expect(satelliteLegendEntry).toHaveText(
      'Configured X-band satellitesNo valid configured satellites'
    );
    await expect(
      page.locator('.globe-marker-label', { hasText: /\S/ })
    ).toHaveCount(0);
  });
  test('reports unavailable configured GEO geometry when the selected satellite is invalid', async ({
    page,
  }) => {
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: '2026-06-21T12:00:00.000Z',
          position: {
            latitude: 12,
            longitude: -60,
            altitude: 35_000,
          },
          ground_entry_point: null,
        },
      });
    });
    await page.route('**/api/satellites', async (route) => {
      await route.fulfill({
        json: [
          {
            satellite_id: 'X-Atlantic',
            transport: 'X',
            longitude: 181,
          },
        ],
      });
    });
    await page.route('**/api/active-x-link', async (route) => {
      await route.fulfill({
        json: {
          satellite_id: 'X-Atlantic',
        },
      });
    });
    await page.goto('/overview');
    const globeLegend = page.getByLabel('Globe legend');
    await expect(
      globeLegend.getByText('Selected configured satellite X-Atlantic', {
        exact: true,
      })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('Configured GEO geometry unavailable', {
        exact: true,
      })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('No valid configured satellites', {
        exact: true,
      })
    ).toBeVisible();
    await expect(page.getByText('X-Atlantic', { exact: true })).toHaveCount(0);
  });
  test('requests and reports a shared aircraft-history trail', async ({
    page,
  }) => {
    const historyRequests: string[] = [];
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: {
            latitude: 10,
            longitude: 175,
          },
          ground_entry_point: null,
        },
      });
    });
    await page.route('**/api/overview-history', async (route) => {
      historyRequests.push(route.request().url());
      await route.fulfill({
        json: {
          window_seconds: 1800,
          start_timestamp_seconds: 1_781_998_200,
          end_timestamp_seconds: 1_782_000_000,
          step_seconds: 1,
          series: {
            starlink_dish_latitude_degrees: [
              [1_781_999_999, 10],
              [1_782_000_000, 10],
            ],
            starlink_dish_longitude_degrees: [
              [1_781_999_999, 175],
              [1_782_000_000, -179],
            ],
          },
        },
      });
    });
    await page.goto('/overview');
    const globeLegend = page.getByLabel('Globe legend');
    await expect(
      globeLegend.getByText('Aircraft history', { exact: true })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('2 trail points', { exact: true })
    ).toBeVisible();
    await expect.poll(() => historyRequests).toHaveLength(1);
    expect(historyRequests[0]).toMatch(/\/api\/overview-history$/);
  });
  test('reports unavailable aircraft history without replacing live telemetry', async ({
    page,
  }) => {
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: {
            latitude: 10,
            longitude: -179,
          },
          ground_entry_point: null,
        },
      });
    });
    await page.route('**/api/overview-history', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        json: {
          detail: 'Overview history is temporarily unavailable',
        },
      });
    });
    await page.goto('/overview');
    const globeLegend = page.getByLabel('Globe legend');
    await expect(
      globeLegend.getByText('Aircraft history', { exact: true })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('Aircraft history unavailable', { exact: true })
    ).toBeVisible();
    await expect(
      globeLegend.getByText('Live telemetry', { exact: true })
    ).toBeVisible();
  });
  test('updates the aircraft history window and refetches shared history', async ({
    page,
  }) => {
    let selectedWindow = 1800;
    const historyRequests: string[] = [];
    const settingsUpdates: number[] = [];
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: {
            latitude: 10,
            longitude: -179,
          },
          ground_entry_point: null,
        },
      });
    });
    await page.route('**/api/overview-history', async (route) => {
      historyRequests.push(route.request().url());
      await route.fulfill({
        json: {
          window_seconds: selectedWindow,
          start_timestamp_seconds: 1_781_998_200,
          end_timestamp_seconds: 1_782_000_000,
          step_seconds: 1,
          series: {},
        },
      });
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      const request = route.request();
      if (request.method() === 'PUT') {
        const update = request.postDataJSON() as {
          window_seconds: number;
        };
        selectedWindow = update.window_seconds;
        settingsUpdates.push(selectedWindow);
      }
      await route.fulfill({
        json: {
          window_seconds: selectedWindow,
        },
      });
    });
    await page.goto('/overview');
    const historyWindow = page.getByLabel('Aircraft history window');
    await expect(historyWindow).toHaveValue('1800');
    await historyWindow.selectOption('900');
    await expect.poll(() => settingsUpdates).toEqual([900]);
    await expect(historyWindow).toHaveValue('900');
    await expect.poll(() => historyRequests.length).toBeGreaterThanOrEqual(2);
  });
  test('renders retained stars and the five-row upcoming POI quick reference at 1920x1080', async ({
    page,
  }) => {
    test.setTimeout(60_000);
    const now = '2026-09-22T12:00:00.000Z';
    const activeMissionPois = {
      state: 'available' as const,
      calculated_at: now,
      pois: [
        {
          poi_id: 'departure-kadw',
          name: 'KADW',
          kind: 'departure' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T10:00:00.000Z',
          eta_seconds: -7_200,
          estimated_arrival_time: '2026-09-22T10:00:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: false,
          map_retained: true,
        },
        {
          poi_id: 'aar-passed',
          name: 'AAR complete',
          kind: 'aar_end' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T11:30:00.000Z',
          eta_seconds: -1_800,
          estimated_arrival_time: '2026-09-22T11:30:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: false,
          map_retained: true,
        },
        {
          poi_id: 'arrival-rkso',
          name: 'RKSO',
          kind: 'arrival' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T14:00:00.000Z',
          eta_seconds: 7_200,
          estimated_arrival_time: '2026-09-22T14:00:00.000Z',
          eta_type: 'anticipated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'x-band',
          name: 'X-band handoff',
          kind: 'x_band_transition' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T12:45:00.000Z',
          eta_seconds: 2_700,
          estimated_arrival_time: '2026-09-22T12:45:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'ka-entry',
          name: 'Ka entry',
          kind: 'ka_coverage_entry' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T12:35:00.000Z',
          eta_seconds: 2_100,
          estimated_arrival_time: '2026-09-22T12:35:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'ka-swap',
          name: 'Ka swap',
          kind: 'ka_transition' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T12:20:00.000Z',
          eta_seconds: 1_200,
          estimated_arrival_time: '2026-09-22T12:20:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'aar-start',
          name: 'AAR start',
          kind: 'aar_start' as const,
          latitude: 0,
          longitude: -90,
          expected_arrival_time: '2026-09-22T12:10:00.000Z',
          eta_seconds: 600,
          estimated_arrival_time: '2026-09-22T12:10:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
        {
          poi_id: 'ka-exit',
          name: 'Ka exit',
          kind: 'ka_coverage_exit' as const,
          latitude: 0,
          longitude: -50,
          expected_arrival_time: '2026-09-22T13:30:00.000Z',
          eta_seconds: 5_400,
          estimated_arrival_time: '2026-09-22T13:30:00.000Z',
          eta_type: 'estimated' as const,
          upcoming: true,
          map_retained: true,
        },
      ],
    };

    await page.addInitScript(`
      const RealDate = Date;
      const fixedTime = '${now}';

      class FixedDate extends RealDate {
        constructor(...args) {
          super(args.length === 0 ? fixedTime : args[0]);
        }

        static now() {
          return new RealDate(fixedTime).getTime();
        }
      }

      window.Date = FixedDate;
    `);
    await page.route('**/api/overview/upcoming-pois', (route) =>
      route.fulfill({
        json: {
          ...activeMissionPois,
          pois: [
            activeMissionPois.pois[6],
            activeMissionPois.pois[5],
            activeMissionPois.pois[4],
            activeMissionPois.pois[3],
            activeMissionPois.pois[2],
            activeMissionPois.pois[0],
            activeMissionPois.pois[1],
            activeMissionPois.pois[7],
          ],
        },
      })
    );

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day-hi.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');
    await waitForGlobeVisualReady(page, earthTexture);

    expect(
      await page.evaluate(() => ({
        width: window.innerWidth,
        height: window.innerHeight,
        visualWidth: window.visualViewport?.width,
        visualHeight: window.visualViewport?.height,
        devicePixelRatio: window.devicePixelRatio,
      }))
    ).toEqual({
      width: 1920,
      height: 1080,
      visualWidth: 1920,
      visualHeight: 1080,
      devicePixelRatio: 1,
    });

    const panel = page.getByLabel('Upcoming POIs');
    await expect(panel).toBeVisible();
    await expect(panel.getByRole('row')).toHaveCount(6);
    await expect(panel.getByRole('columnheader', { name: /urgency/i })).toHaveCount(0);
    await expect(panel.getByRole('columnheader', { name: 'Type' })).toBeVisible();
    await expect(panel).toHaveCSS('overflow-y', 'hidden');
    await expect(panel.getByText('AAR complete', { exact: true })).toHaveCount(0);
    await expect(page.getByText('KADW', { exact: true })).toBeVisible();
    await expect(panel.getByText('RKSO', { exact: true })).toBeVisible();
    await expect(page.getByText('AAR complete', { exact: true })).toBeVisible();
    await expect(panel.getByRole('row')).toHaveText([
      /POI.*Type.*ETA/,
      /AAR start.*AAR start.*2026-09-22 12:10 UTC · estimated/,
      /Ka swap.*Ka transition.*2026-09-22 12:20 UTC · estimated/,
      /Ka entry.*Ka coverage entry.*2026-09-22 12:35 UTC · estimated/,
      /X-band handoff.*X-band transition.*2026-09-22 12:45 UTC · estimated/,
      /RKSO.*Arrival.*2026-09-22 14:00 UTC · anticipated/,
    ]);
    const clusteredPoiIds = [
      'departure-kadw',
      'aar-passed',
      'arrival-rkso',
      'x-band',
      'ka-entry',
      'ka-swap',
      'aar-start',
      'ka-exit',
    ];
    const fallback = page.locator('[data-poi-label-fallback="true"]');
    if (await fallback.count()) {
      await expect(fallback).toBeVisible();
      await expect(fallback).toContainText(/POIs — see Upcoming POIs/);
    } else {
      const clusteredLabels = await Promise.all(
        clusteredPoiIds.map(async (poiId) => {
          const label = page.locator(`[data-poi-label="${poiId}"]`);
          await expect(label).toBeVisible();
          const box = await label.boundingBox();
          expect(box).not.toBeNull();
          return box!;
        })
      );
      for (let index = 0; index < clusteredLabels.length; index += 1) {
        for (let other = index + 1; other < clusteredLabels.length; other += 1) {
          const first = clusteredLabels[index];
          const second = clusteredLabels[other];
          expect(
            first.x + first.width <= second.x ||
              second.x + second.width <= first.x ||
              first.y + first.height <= second.y ||
              second.y + second.height <= first.y
          ).toBe(true);
        }
      }
    }
    await expect(panel.locator('.upcoming-pois__swatch')).toHaveCount(5);
    await expect(panel.locator('.upcoming-pois__swatch').nth(0)).toHaveCSS(
      'background-color',
      'rgb(241, 115, 53)'
    );
    await expect(panel.locator('.upcoming-pois__swatch').nth(4)).toHaveCSS(
      'background-color',
      'rgb(34, 197, 94)'
    );
    await expect(page).toHaveScreenshot('overview-upcoming-pois-1920x1080.png', {
      animations: 'disabled',
      maxDiffPixelRatio: 0.02,
    });
  });

  test('retains a persisted custom aircraft history window', async ({
    page,
  }) => {
    await page.route('**/api/routes', async (route) => {
      await route.fulfill({
        json: {
          routes: [],
          total: 0,
        },
      });
    });
    await page.route('**/api/status', async (route) => {
      await route.fulfill({
        json: {
          timestamp: new Date().toISOString(),
          position: {
            latitude: 10,
            longitude: -179,
          },
          ground_entry_point: null,
        },
      });
    });
    await page.route('**/api/overview-history/settings', async (route) => {
      await route.fulfill({
        json: {
          window_seconds: 1200,
        },
      });
    });
    await page.goto('/overview');
    await expect(page.getByLabel('Aircraft history window')).toHaveValue(
      '1200'
    );
  });
});
