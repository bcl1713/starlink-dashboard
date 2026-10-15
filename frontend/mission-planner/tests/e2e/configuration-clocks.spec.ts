import { expect, test } from '@playwright/test';

const clocks = [
  { label: 'Zulu / UTC', time_zone: 'UTC' },
  { label: 'Washington, DC', time_zone: 'America/New_York' },
  { label: 'Omaha, NE', time_zone: 'America/Chicago' },
  { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
];

test.describe('Configuration Clocks', () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/overview-clocks/settings', async (route) => {
      if (route.request().method() === 'PUT') {
        await route.fulfill({
          json: route.request().postDataJSON(),
        });
        return;
      }
      await route.fulfill({
        json: { clocks },
      });
    });
    await page.route('**/api/v2/gps/config', async (route) => {
      await route.fulfill({
        json: {
          enabled: true,
          ready: true,
          satellites: 4,
        },
      });
    });
  });

  test('renders major page elements as expected', async ({ page }) => {
    await page.goto('/configuration');
    await expect(page.getByLabel('Clock 1 label')).toBeVisible();
    await expect(page.getByLabel('Clock 4 timezone')).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Save operational clocks' })
    ).toBeVisible();
    await expect(
      page.getByRole('heading', {
        name: 'Operational clocks',
      })
    ).toBeVisible();
  });

  test('saves edited clock settings', async ({ page }) => {
    await page.goto('/configuration');
    await page.getByLabel('Clock 3 label').fill('Andrews AFB, MD');
    const updateRequest = page.waitForRequest(
      (request) =>
        request.url().endsWith('/api/overview-clocks/settings') &&
        request.method() === 'PUT'
    );
    await page
      .getByRole('button', {
        name: 'Save operational clocks',
      })
      .click();
    const request = await updateRequest;
    expect(request.postDataJSON()).toEqual({
      clocks: [
        { label: 'Zulu / UTC', time_zone: 'UTC' },
        {
          label: 'Washington, DC',
          time_zone: 'America/New_York',
        },
        {
          label: 'Andrews AFB, MD',
          time_zone: 'America/Chicago',
        },
        { label: 'Tokyo, JP', time_zone: 'Asia/Tokyo' },
      ],
    });
  });
});
