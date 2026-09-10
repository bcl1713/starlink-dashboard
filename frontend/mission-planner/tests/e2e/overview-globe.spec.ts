import { expect, test } from '@playwright/test';

test.describe('Globe overview', () => {
  test.describe.configure({ mode: 'serial' });
  test.use({ viewport: { width: 1920, height: 1080 } });

  test('renders an active anti-meridian route from same-origin API data', async ({
    page,
  }) => {
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

    await expect(page.getByLabel('Active route legend')).toBeVisible();
    await expect(page.getByText('GEP', { exact: true })).toBeVisible();
    await expect(
      page.getByText('Anti-meridian validation route', { exact: true })
    ).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible();
    await expect.poll(() => routeRequests).toHaveLength(2);
    await expect(earthTexture).resolves.toBeTruthy();

    expect(routeRequests[0]).toMatch(/\/api\/routes$/);
    expect(routeRequests[1]).toMatch(/\/api\/routes\/active-anti-meridian$/);
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
          routes: [],
          total: 0,
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
    await expect(
      page.getByText('GEP unavailable', { exact: true })
    ).toBeVisible();
  });
});
