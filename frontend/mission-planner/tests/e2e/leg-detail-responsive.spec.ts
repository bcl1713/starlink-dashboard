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
            { latitude: 50, longitude: -50 },
            { latitude: 30, longitude: -50 },
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
      const request = route.request();
      const hasManualTrack =
        request.method() === 'POST' &&
        request.postDataJSON().transports.manual_aar_tracks.length > 0;
      await route.fulfill({
        json: {
          mission_leg_id: 'responsive-leg',
          created_at: '2026-08-13T00:00:00Z',
          segments: hasManualTrack
            ? [
                {
                  id: 'manual-ar-segment',
                  start_time: '2026-08-13T00:30:00Z',
                  end_time: '2026-08-13T01:30:00Z',
                  status: 'degraded',
                  x_state: 'degraded',
                  ka_state: 'available',
                  ku_state: 'available',
                  reasons: ['Manual AR Track: Manual AR Track'],
                },
              ]
            : [],
          statistics: hasManualTrack
            ? {
                total_duration_seconds: 7200,
                degraded_seconds: 3600,
                critical_seconds: 0,
                nominal_seconds: 3600,
              }
            : undefined,
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
  test('persists a manual AR track without crypto.randomUUID on mobile', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => {
      Object.defineProperty(globalThis.crypto, 'randomUUID', {
        configurable: true,
        value: undefined,
      });
    });
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

    await expect(page.getByText('2 operator-entered points')).toBeVisible();
    const manualTrackOverlay = page.locator(
      'path[stroke="var(--route-manual-track)"]'
    );
    await expect(manualTrackOverlay).toBeAttached();
    await expect(manualTrackOverlay).not.toHaveAttribute('d', 'M0 0');
    await expect(page.getByText('1 segments')).toBeVisible();
    await expect(page.getByText('Degraded Time')).toBeVisible();
    await expect(
      page.getByText('Degraded Time').locator('..').getByText('60m')
    ).toBeVisible();

    await page.reload();
    await page.getByRole('tab', { name: 'Manual AR Tracks' }).click();
    await expect(page.getByText('2 operator-entered points')).toBeVisible();
    await expect(
      page.locator('path[stroke="var(--route-manual-track)"]')
    ).toBeAttached();
  });

  test('hydrates persisted manual AR track points for no-op save and reload', async ({
    page,
  }) => {
    const persistedMission = {
      ...mission,
      legs: mission.legs.map((leg) => ({
        ...leg,
        transports: {
          ...leg.transports,
          manual_aar_tracks: [
            {
              id: 'persisted-manual-ar-track',
              name: 'Persisted Manual AR Track',
              points: [
                { latitude: 50, longitude: -50 },
                { latitude: 30, longitude: -50 },
              ],
            },
          ],
        },
      })),
    };
    let savedManualTracks: Array<{
      id: string;
      name: string;
      points: Array<{ latitude: number; longitude: number }>;
    }> = [];

    await mockLegDetailApis(page);
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission',
      async (route) => {
        await route.fulfill({ json: persistedMission });
      }
    );
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission/legs/responsive-leg',
      async (route) => {
        if (route.request().method() !== 'PUT') {
          await route.continue();
          return;
        }

        const updatedLeg = route.request().postDataJSON();
        savedManualTracks = updatedLeg.transports.manual_aar_tracks;
        persistedMission.legs[0] = updatedLeg;
        await route.fulfill({ json: { leg: updatedLeg, warnings: [] } });
      }
    );

    await page.goto('/missions/responsive-mission/legs/responsive-leg');
    await page.getByRole('tab', { name: 'Manual AR Tracks' }).click();

    await expect(page.getByLabel('Manual AR track name')).toHaveValue(
      'Persisted Manual AR Track'
    );
    await expect(page.getByLabel('Manual AR point 1 latitude')).toHaveValue(
      '50'
    );
    await expect(page.getByLabel('Manual AR point 1 longitude')).toHaveValue(
      '-50'
    );
    await expect(page.getByLabel('Manual AR point 2 latitude')).toHaveValue(
      '30'
    );
    await expect(page.getByLabel('Manual AR point 2 longitude')).toHaveValue(
      '-50'
    );

    await page
      .getByRole('button', { name: 'Save and Persist Manual AR Track' })
      .click();
    await expect(page.getByRole('status')).toHaveText('Manual AR track saved.');
    await expect
      .poll(() => savedManualTracks)
      .toEqual([
        {
          id: 'persisted-manual-ar-track',
          name: 'Persisted Manual AR Track',
          points: [
            { latitude: 50, longitude: -50 },
            { latitude: 30, longitude: -50 },
          ],
        },
      ]);

    await page.reload();
    await page.getByRole('tab', { name: 'Manual AR Tracks' }).click();
    await expect(page.getByLabel('Manual AR point 1 latitude')).toHaveValue(
      '50'
    );
    await expect(page.getByLabel('Manual AR point 2 longitude')).toHaveValue(
      '-50'
    );
    await expect(
      page.locator('path[stroke="var(--route-manual-track)"]')
    ).toBeAttached();
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

  test('keeps navigation and every tab reachable without mobile page overflow', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockLegDetailApis(page);

    await page.goto('/missions/responsive-mission/legs/responsive-leg');

    const navigationLinks = [
      'Missions',
      'Satellites',
      'POIs',
      'Routes',
      'Data Export',
      'Configuration',
    ];
    const tabNames = [
      'X-Band',
      'Ka Outages',
      'Ku/Starlink Outages',
      'AAR Segments',
      'Manual AR Tracks',
    ];
    const manualArTab = page.getByRole('tab', { name: 'Manual AR Tracks' });
    const mapHeading = page.getByRole('heading', {
      name: 'Route Visualization',
    });

    await page.getByRole('button', { name: 'Toggle navigation' }).click();
    const hasPageOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth
    );
    expect(hasPageOverflow).toBe(false);
    for (const linkName of navigationLinks) {
      await expect(
        page.getByRole('link', { name: linkName, exact: true })
      ).toBeInViewport();
    }
    for (const tabName of tabNames) {
      const tab = page.getByRole('tab', { name: tabName });
      await tab.scrollIntoViewIfNeeded();
      await expect(tab).toBeInViewport();
    }
    await expect(mapHeading).toBeVisible();

    const [tabBox, mapBox] = await Promise.all([
      manualArTab.boundingBox(),
      mapHeading.boundingBox(),
    ]);
    expect(tabBox).not.toBeNull();
    expect(mapBox).not.toBeNull();
    expect(mapBox!.y).toBeGreaterThan(tabBox!.y);

    await manualArTab.focus();
    await expect(manualArTab).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(
      page.getByRole('heading', { name: 'Manual AR Track', exact: true })
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

  test('adds, saves, reloads, and previews a Ka outage from duration hours on mobile', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const persistedMission = structuredClone(mission);
    let savedKaOutages: Array<{ duration_seconds: number }> = [];
    let previewKaOutages: Array<{ duration_seconds: number }> = [];

    await mockLegDetailApis(page);
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission',
      async (route) => {
        await route.fulfill({ json: persistedMission });
      }
    );
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission/legs/responsive-leg',
      async (route) => {
        if (route.request().method() !== 'PUT') {
          await route.continue();
          return;
        }

        const updatedLeg = route.request().postDataJSON();
        savedKaOutages = updatedLeg.transports.ka_outages;
        persistedMission.legs[0] = updatedLeg;
        await route.fulfill({ json: { leg: updatedLeg, warnings: [] } });
      }
    );
    await page.route(
      'http://localhost:8000/api/v2/missions/responsive-mission/legs/responsive-leg/timeline/preview',
      async (route) => {
        if (route.request().method() === 'POST') {
          previewKaOutages = route.request().postDataJSON()
            .transports.ka_outages;
        }
        await route.fulfill({
          json: {
            mission_leg_id: 'responsive-leg',
            created_at: '2026-08-13T00:00:00Z',
            segments: [],
          },
        });
      }
    );

    await page.goto('/missions/responsive-mission/legs/responsive-leg');
    await page.getByRole('tab', { name: 'Ka Outages' }).click();

    const startTime = page.getByLabel('Ka outage start time');
    const duration = page.getByLabel('Duration (hours)');
    const endTime = page.getByLabel('Calculated Ka outage end time');
    const addOutage = page.getByRole('button', { name: 'Add', exact: true });

    await expect(duration).toHaveAttribute('type', 'text');
    await expect(duration).toHaveAttribute('inputmode', 'decimal');
    await expect(duration).toHaveAttribute('pattern', '[+-]?[0-9]*\\.?[0-9]*');
    await expect(duration).toHaveAttribute('min', '0.01');
    await expect(duration).toHaveAttribute('max', '24');
    await startTime.fill('2026-08-13T00:30');
    await duration.fill('1.5');
    await expect(endTime).toHaveValue('2026-08-13T02:00');

    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth
      )
    ).toBe(false);
    await addOutage.scrollIntoViewIfNeeded();
    await expect(addOutage).toBeInViewport();
    await addOutage.click();

    await expect.poll(() => previewKaOutages[0]?.duration_seconds).toBe(5400);
    await expect(page.getByText('1.50', { exact: true })).toBeVisible();

    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expect.poll(() => savedKaOutages[0]?.duration_seconds).toBe(5400);

    await page.reload();
    await page.getByRole('tab', { name: 'Ka Outages' }).click();
    await expect(page.getByText('1.50', { exact: true })).toBeVisible();
  });

  test('keeps invalid Ka outage values and explains how to correct them', async ({
    page,
  }) => {
    await mockLegDetailApis(page);
    await page.goto('/missions/responsive-mission/legs/responsive-leg');
    await page.getByRole('tab', { name: 'Ka Outages' }).click();

    const startTime = page.getByLabel('Ka outage start time');
    const duration = page.getByLabel('Duration (hours)');
    const addOutage = page.getByRole('button', { name: 'Add', exact: true });

    await addOutage.click();
    await expect(page.getByText('Datetime is required')).toBeVisible();
    await expect(page.getByText('Duration is required.')).toBeVisible();

    await startTime.fill('2026-08-13T00:30');
    await duration.fill('0');
    await addOutage.click();
    await expect(
      page.getByText('Duration must be greater than 0 hours.')
    ).toBeVisible();
    await expect(duration).toHaveValue('0');

    await duration.fill('-1');
    await addOutage.click();
    await expect(
      page.getByText('Duration must be greater than 0 hours.')
    ).toBeVisible();
    await expect(duration).toHaveValue('-1');

    await duration.fill('25');
    await addOutage.click();
    await expect(
      page.getByText('Duration cannot exceed 24 hours.')
    ).toBeVisible();
    await expect(duration).toHaveValue('25');

    await duration.fill('abc');
    await addOutage.click();
    await expect(
      page.getByText('Enter a valid number of hours.')
    ).toBeVisible();
    await expect(duration).toHaveValue('abc');

    await duration.fill('1e-1');
    await addOutage.click();
    await expect(
      page.getByText('Enter a valid number of hours.')
    ).toBeVisible();
    await expect(duration).toHaveValue('1e-1');
  });
});
