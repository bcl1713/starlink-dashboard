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

    const earthTexture = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/earth-day.jpg' &&
        response.status() === 200
    );

    await page.goto('/overview');

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
});
