import { test, expect } from '@playwright/test';

test('loads saved POI fields before editing and preserves them when saving', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const poi = {
    id: 'saved-poi',
    name: 'Greenwich waypoint',
    latitude: 51.48,
    longitude: 0,
    icon: '📍',
    category: 'waypoint',
    description: 'Keep this saved description',
    route_id: null,
    mission_id: null,
    active: true,
    created_at: '2026-10-03T00:00:00Z',
    updated_at: '2026-10-03T00:00:00Z',
  };
  await page.route('**/api/pois**', (route) =>
    route.fulfill({ json: { pois: [poi], total: 1 } })
  );
  await page.route('**/api/routes**', (route) =>
    route.fulfill({ json: { routes: [], total: 0 } })
  );
  await page.route('**/api/v2/missions**', (route) =>
    route.fulfill({ json: [] })
  );
  await page.route('**/*.tile.openstreetmap.org/**', (route) => route.abort());

  let releaseDetail!: () => void;
  const detailReady = new Promise<void>((resolve) => {
    releaseDetail = resolve;
  });
  await page.route('**/api/pois/saved-poi', async (route) => {
    if (route.request().method() === 'GET') {
      await detailReady;
      await route.fulfill({ json: poi });
    } else {
      await route.fulfill({ json: poi });
    }
  });

  await page.goto('/pois');
  const detailRequested = page.waitForRequest('**/api/pois/saved-poi');
  await page
    .getByRole('row')
    .filter({ hasText: 'Greenwich waypoint' })
    .getByRole('button')
    .nth(1)
    .click();
  await detailRequested;
  const dialog = page.getByRole('dialog');
  await expect(
    dialog.getByRole('button', { name: 'Saving...' })
  ).toBeDisabled();
  releaseDetail();

  await expect(dialog.getByLabel('Name *')).toHaveValue('Greenwich waypoint');
  await expect(dialog.getByLabel('Category *')).toHaveValue('waypoint');
  await expect(dialog.getByLabel('Description')).toHaveValue(
    'Keep this saved description'
  );
  await expect(dialog.getByLabel('Latitude *')).toHaveValue('51.48');
  await expect(dialog.getByLabel('Longitude *')).toHaveValue('0');

  await dialog.getByLabel('Name *').fill('Renamed waypoint');
  const saved = page.waitForRequest(
    (request) =>
      request.url().endsWith('/api/pois/saved-poi') &&
      request.method() === 'PUT'
  );
  await dialog.getByRole('button', { name: 'Save POI' }).click();
  expect((await saved).postDataJSON()).toMatchObject({
    name: 'Renamed waypoint',
    category: 'waypoint',
    description: 'Keep this saved description',
    latitude: 51.48,
    longitude: 0,
  });
  await expect(dialog).toBeHidden();
});
