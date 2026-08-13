import { expect, test, type Page } from '@playwright/test';

const mission = {
  id: 'responsive-mission',
  name: 'Responsive Mission',
  description: 'Leg layout test fixture',
  created_at: '2026-08-13T00:00:00Z',
  updated_at: '2026-08-13T00:00:00Z',
  metadata: {},
  legs: [
    {
      id: 'responsive-leg',
      name: 'Responsive Leg',
      route_id: 'responsive-route',
      transports: {
        initial_x_satellite_id: 'X-1',
        initial_ka_satellite_ids: ['AOR', 'POR', 'IOR'],
        x_transitions: [],
        ka_outages: [],
        aar_windows: [],
        manual_aar_tracks: [],
        ku_overrides: [],
      },
    },
  ],
};

async function mockLegDetailApis(page: Page) {
  await page.route(
    'http://localhost:8000/api/v2/missions/responsive-mission',
    async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ json: mission });
        return;
      }
      await route.continue();
    }
  );

  await page.route(
    'http://localhost:8000/api/routes/responsive-route',
    async (route) => {
      await route.fulfill({
        json: {
          points: [
            { latitude: 34, longitude: -118 },
            { latitude: 35, longitude: -117 },
          ],
          waypoints: [],
        },
      });
    }
  );

  await page.route(
    'http://localhost:8000/api/v2/missions/responsive-mission/legs/responsive-leg/timeline',
    async (route) => {
      await route.fulfill({
        json: {
          mission_leg_id: 'responsive-leg',
          created_at: '2026-08-13T00:00:00Z',
          segments: [],
        },
      });
    }
  );

  await page.route(
    'http://localhost:8000/api/v2/missions/responsive-mission/legs/responsive-leg/timeline/preview',
    async (route) => {
      await route.fulfill({
        json: {
          mission_leg_id: 'responsive-leg',
          created_at: '2026-08-13T00:00:00Z',
          segments: [],
        },
      });
    }
  );

  await page.route('http://localhost:8000/api/satellites', async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.route('http://localhost:8000/api/pois**', async (route) => {
    await route.fulfill({ json: { pois: [], total: 0 } });
  });
}

test.describe('Leg detail responsive layout', () => {
  test('persists a manual AR track, confirms it, and retains it after reload', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const persistedMission = structuredClone(mission);

    await mockLegDetailApis(page);
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission/legs/responsive-leg',
      async (route) => {
        if (route.request().method() !== 'PUT') {
          await route.continue();
          return;
        }

        const updatedLeg = route.request().postDataJSON();
        persistedMission.legs[0] = updatedLeg;
        await route.fulfill({ json: { leg: updatedLeg, warnings: [] } });
      }
    );
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission',
      async (route) => {
        await route.fulfill({ json: persistedMission });
      }
    );

    await page.goto('/missions/responsive-mission/legs/responsive-leg');
    await page.getByRole('tab', { name: 'Manual AR Tracks' }).click();
    await page.getByLabel('Manual AR point 1 latitude').fill('50');
    await page.getByLabel('Manual AR point 1 longitude').fill('-50');
    await page.getByLabel('Manual AR point 2 latitude').fill('30');
    await page.getByLabel('Manual AR point 2 longitude').fill('-50');

    const saveTrack = page.getByRole('button', {
      name: 'Save and Persist Manual AR Track',
    });
    await saveTrack.scrollIntoViewIfNeeded();
    await expect(saveTrack).toBeInViewport();
    await saveTrack.click();

    await expect(page.getByRole('status')).toHaveText('Manual AR track saved.');
    await expect(page.getByText('2 operator-entered points')).toBeVisible();

    await page.reload();
    await page.getByRole('tab', { name: 'Manual AR Tracks' }).click();
    await expect(page.getByText('2 operator-entered points')).toBeVisible();
  });

  test('keeps invalid manual AR track input and shows an inline error', async ({
    page,
  }) => {
    await mockLegDetailApis(page);
    await page.goto('/missions/responsive-mission/legs/responsive-leg');
    await page.getByRole('tab', { name: 'Manual AR Tracks' }).click();
    await page.getByLabel('Manual AR point 1 latitude').fill('50');
    await page.getByLabel('Manual AR point 1 longitude').fill('-50');
    await page.getByLabel('Manual AR point 2 latitude').fill('30');

    await page
      .getByRole('button', { name: 'Save and Persist Manual AR Track' })
      .click();

    await expect(page.getByRole('alert')).toHaveText(
      'Enter both latitude and longitude for every manual AR track point.'
    );
    await expect(page.getByLabel('Manual AR point 1 latitude')).toHaveValue(
      '50'
    );
    await expect(page.getByLabel('Manual AR point 2 latitude')).toHaveValue(
      '30'
    );
  });

  test('stacks the map and keeps Manual AR Tracks reachable on mobile', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockLegDetailApis(page);

    await page.goto('/missions/responsive-mission/legs/responsive-leg');

    const manualArTab = page.getByRole('tab', { name: 'Manual AR Tracks' });
    const mapHeading = page.getByRole('heading', {
      name: 'Route Visualization',
    });

    await expect(manualArTab).toBeVisible();
    await expect(mapHeading).toBeVisible();
    await manualArTab.scrollIntoViewIfNeeded();
    await expect(manualArTab).toBeInViewport();

    const [tabBox, mapBox] = await Promise.all([
      manualArTab.boundingBox(),
      mapHeading.boundingBox(),
    ]);
    expect(tabBox).not.toBeNull();
    expect(mapBox).not.toBeNull();
    expect(mapBox!.y).toBeGreaterThan(tabBox!.y);

    await manualArTab.click();
    await expect(
      page.getByRole('heading', { name: 'Manual AR Track' })
    ).toBeVisible();
  });

  test('keeps both panels and the complete tab strip inside a narrow desktop viewport', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await mockLegDetailApis(page);

    await page.goto('/missions/responsive-mission/legs/responsive-leg');

    const manualArTab = page.getByRole('tab', { name: 'Manual AR Tracks' });
    const mapHeading = page.getByRole('heading', {
      name: 'Route Visualization',
    });

    await expect(manualArTab).toBeVisible();
    await manualArTab.scrollIntoViewIfNeeded();
    await expect(manualArTab).toBeInViewport();
    await expect(mapHeading).toBeVisible();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth
    );
    expect(overflow).toBe(false);
  });
});
