import { expect, test } from '@playwright/test';

test.describe('Mission Planner API origin', () => {
  test('loads an empty mission collection through the same-origin API proxy', async ({
    page,
  }) => {
    const missionRequests: string[] = [];

    await page.route(
      'http://localhost:5173/api/v2/missions**',
      async (route) => {
        missionRequests.push(route.request().url());
        await route.fulfill({
          headers: { 'X-Total-Count': '0' },
          json: [],
        });
      }
    );

    await page.goto('/missions');

    await expect(
      page.getByText('No missions yet', { exact: true })
    ).toBeVisible();
    await expect(page.getByText(/Error loading missions/)).not.toBeVisible();
    expect(missionRequests).toHaveLength(1);
    expect(missionRequests[0]).toMatch(
      /^http:\/\/localhost:5173\/api\/v2\/missions\?/
    );
  });

  test('downloads data exports through the same-origin API proxy', async ({
    page,
  }) => {
    const exportRequests: string[] = [];

    await page.route(
      'http://localhost:5173/api/export/starlink-csv**',
      async (route) => {
        exportRequests.push(route.request().url());
        await route.fulfill({
          headers: { 'Content-Type': 'text/csv' },
          body: 'timestamp,latitude\n',
        });
      }
    );

    await page.goto('/export');
    await page.getByRole('button', { name: 'Export CSV' }).click();

    await expect.poll(() => exportRequests).toHaveLength(1);
    expect(exportRequests[0]).toMatch(
      /^http:\/\/localhost:5173\/api\/export\/starlink-csv\?/
    );
  });
});
