import { expect, test } from '@playwright/test';

test.describe('Globe overview', () => {
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
            latitude: 0,
            longitude: 179,
          },
        },
      });
    });

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');

    await expect(
      page.getByText('Live telemetry', { exact: true })
    ).toBeVisible();

    await expect.poll(() => statusRequests).toHaveLength(1);

    expect(statusRequests[0]).toMatch(/\/api\/status$/);

    await expect(page.getByLabel('Active route legend')).toBeVisible();
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
    let statusRequestCount = 0;
    let inFlightRequests = 0;
    let maximumInFlightRequests = 0;

    await page.route('**/api/status', async (route) => {
      statusRequestCount += 1;
      inFlightRequests += 1;
      maximumInFlightRequests = Math.max(
        maximumInFlightRequests,
        inFlightRequests
      );

      try {
        await new Promise((resolve) => setTimeout(resolve, 1_500));

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

    await expect
      .poll(() => statusRequestCount, { timeout: 5_000 })
      .toBeGreaterThanOrEqual(2);

    expect(maximumInFlightRequests).toBe(1);
  });
});
