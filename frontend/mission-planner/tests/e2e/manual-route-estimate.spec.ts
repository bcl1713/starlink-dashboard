import { expect, test, type Page } from '@playwright/test';

const mission = {
  id: 'manual-route-mission',
  name: 'Manual Route Mission',
  description: 'Manual AR derived-estimate fixture',
  created_at: '2026-08-26T00:00:00Z',
  updated_at: '2026-08-26T00:00:00Z',
  metadata: {},
  legs: [
    {
      id: 'manual-route-leg',
      name: 'Manual Route Leg',
      route_id: 'manual-route',
      transports: {
        initial_x_satellite_id: 'X-1',
        initial_ka_satellite_ids: ['AOR', 'POR', 'IOR'],
        x_transitions: [],
        ka_outages: [],
        aar_windows: [],
        manual_aar_tracks: [
          {
            id: 'feasible-track',
            name: 'Feasible diversion',
            points: [
              { latitude: 50, longitude: -50 },
              { latitude: 30, longitude: -50 },
            ],
          },
          {
            id: 'low-confidence-track',
            name: 'Low confidence diversion',
            points: [
              { latitude: 50, longitude: 170 },
              { latitude: 40, longitude: 179 },
              { latitude: 30, longitude: -179 },
              { latitude: 20, longitude: -170 },
            ],
          },
          {
            id: 'unavailable-track',
            name: 'Remote diversion',
            points: [
              { latitude: -50, longitude: 20 },
              { latitude: -30, longitude: 20 },
            ],
          },
        ],
        ku_overrides: [],
      },
    },
  ],
};

type Splice = {
  enabled_track_id: string;
  leave_segment_index?: number;
  leave_fraction?: number;
  rejoin_segment_index?: number;
  rejoin_fraction?: number;
  speed_knots?: number;
};

function derivedEstimate(
  trackId: string,
  splice?: Splice
): Record<string, unknown> | null {
  if (!splice) return null;
  if (trackId === 'unavailable-track') {
    return {
      available: false,
      estimated: false,
      unavailable_reason: 'no_feasible_splice',
    };
  }

  const antimeridian = trackId === 'low-confidence-track';
  return {
    available: true,
    estimated: true,
    confidence: antimeridian ? 'low' : 'high',
    planned_distance_nm: 1500,
    derived_distance_nm: 1600,
    delta_seconds: 900,
    speed_knots: splice.speed_knots ?? 400,
    speed_source: splice.speed_knots
      ? 'operator_override'
      : 'assumed_400_ktas',
    leave_anchor: {
      segment_index: splice.leave_segment_index ?? 0,
      fraction: splice.leave_fraction ?? 0.25,
      progress_nm: 100,
      latitude: 50,
      longitude: antimeridian ? 170 : -50,
      connector_nm: 20,
    },
    rejoin_anchor: {
      segment_index: splice.rejoin_segment_index ?? 1,
      fraction: splice.rejoin_fraction ?? 0.75,
      progress_nm: 1400,
      latitude: 30,
      longitude: antimeridian ? -170 : -50,
      connector_nm: 20,
    },
    points: antimeridian
      ? [
          { latitude: 50, longitude: 170, provenance: 'planned' },
          { latitude: 40, longitude: 179, provenance: 'manual_ar' },
          { latitude: 30, longitude: -179, provenance: 'manual_ar' },
          { latitude: 20, longitude: -170, provenance: 'planned' },
        ]
      : [
          { latitude: 50, longitude: -50, provenance: 'planned' },
          { latitude: 40, longitude: -50, provenance: 'manual_ar' },
          { latitude: 30, longitude: -50, provenance: 'planned' },
        ],
  };
}

async function mockManualRouteApis(
  page: Page,
  persistedMission: typeof mission,
  onPreviewRouteBasis?: (routeBasis: string) => void
) {
  await page.route('**/api/v2/missions/manual-route-mission', async (route) => {
    await route.fulfill({ json: persistedMission });
  });
  await page.route('**/api/routes/manual-route', async (route) => {
    await route.fulfill({
      json: {
        points: [
          { latitude: 50, longitude: -50 },
          { latitude: 30, longitude: -50 },
        ],
        waypoints: [],
      },
    });
  });
  await page.route(
    '**/api/v2/missions/manual-route-mission/legs/manual-route-leg/timeline',
    async (route) => {
      await route.fulfill({
        json: {
          mission_leg_id: 'manual-route-leg',
          created_at: '2026-08-26T00:00:00Z',
          segments: [],
        },
      });
    }
  );
  await page.route(
    '**/api/v2/missions/manual-route-mission/legs/manual-route-leg/timeline/preview',
    async (route) => {
      const request = route.request().postDataJSON();
      const splice = request.transports.manual_route_splice as Splice | null;
      const estimate = splice
        ? derivedEstimate(splice.enabled_track_id, splice)
        : null;
      const routeBasis = estimate?.available ? 'derived_estimate' : 'planned';
      onPreviewRouteBasis?.(routeBasis);
      await route.fulfill({
        json: {
          mission_leg_id: 'manual-route-leg',
          created_at: '2026-08-26T00:00:00Z',
          segments: [],
          route_basis: routeBasis,
          derived_route_estimate: estimate,
        },
      });
    }
  );
  await page.route('**/api/satellites', async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route('**/api/pois**', async (route) => {
    await route.fulfill({ json: { pois: [], total: 0 } });
  });
}

test.describe('Manual AR derived route estimates', () => {
  test('persists a feasible selected estimate with overrides and explicitly reverts it', async ({
    page,
  }) => {
    const persistedMission = structuredClone(mission);
    let savedSplice: Splice | null | undefined;

    await page.addInitScript(() => {
      window.alert = () => undefined;
    });
    await mockManualRouteApis(page, persistedMission);
    await page.route(
      '**/api/v2/missions/manual-route-mission/legs/manual-route-leg',
      async (route) => {
        if (route.request().method() !== 'PUT') {
          await route.continue();
          return;
        }
        const updatedLeg = route.request().postDataJSON();
        savedSplice = updatedLeg.transports.manual_route_splice;
        persistedMission.legs[0] = updatedLeg;
        await route.fulfill({ json: { leg: updatedLeg, warnings: [] } });
      }
    );

    await page.goto('/missions/manual-route-mission/legs/manual-route-leg');
    const estimateButtons = page.getByRole('button', {
      name: /as estimated route$/,
    });
    await expect(estimateButtons).toHaveText([
      'Use Feasible diversion as estimated route',
      'Use Low confidence diversion as estimated route',
      'Use Remote diversion as estimated route',
    ]);

    const feasible = page.getByRole('button', {
      name: 'Use Feasible diversion as estimated route',
    });
    await feasible.click();
    await expect(feasible).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('status')).toContainText('Estimated route active');
    await expect(page.getByRole('status')).toContainText(
      'Basis: derived estimate; confidence: high.'
    );
    await expect(page.getByRole('status')).toContainText(
      '400 KTAS (assumed 400 KTAS)'
    );
    await expect(
      page.getByText('Estimated map layer: derived estimate, not telemetry.')
    ).toBeVisible();

    await page.getByText('Optional anchor and speed overrides').click();
    await page.getByLabel('Leave segment override').fill('1');
    await page.getByLabel('Leave fraction override').fill('0.2');
    await page.getByLabel('Rejoin segment override').fill('2');
    await page.getByLabel('Rejoin fraction override').fill('0.8');
    await page.getByLabel('Estimated route speed override').fill('450');
    await expect(page.getByRole('status')).toContainText(
      '450 KTAS (operator override)'
    );

    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expect.poll(() => savedSplice).toEqual({
      enabled_track_id: 'feasible-track',
      leave_segment_index: 1,
      leave_fraction: 0.2,
      rejoin_segment_index: 2,
      rejoin_fraction: 0.8,
      speed_knots: 450,
    });

    await page.reload();
    await expect(feasible).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByLabel('Estimated route speed override')).toHaveValue('450');
    await page.getByRole('button', { name: 'Revert to planned route' }).click();
    await expect(feasible).toHaveAttribute('aria-pressed', 'false');
    await expect(
      page.getByRole('button', { name: 'Revert to planned route' })
    ).not.toBeVisible();
  });

  test('shows low-confidence and unavailable planned fallback states on mobile without drawing an antimeridian world span', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const persistedMission = structuredClone(mission);
    let unavailableRouteBasis: string | undefined;
    await mockManualRouteApis(page, persistedMission, (routeBasis) => {
      unavailableRouteBasis = routeBasis;
    });

    await page.goto('/missions/manual-route-mission/legs/manual-route-leg');
    await page
      .getByRole('button', {
        name: 'Use Low confidence diversion as estimated route',
      })
      .click();
    await expect(page.getByRole('status')).toContainText(
      'Basis: derived estimate; confidence: low.'
    );
    await expect(
      page.getByText('Estimated map layer: derived estimate, not telemetry.')
    ).toBeVisible();
    const map = page.getByRole('region', { name: 'Route Visualization' });
    await map.scrollIntoViewIfNeeded();
    await expect(map).toBeInViewport();
    const visibleMapPaths = page.locator(
      'path[stroke="var(--route-manual-track)"][stroke-opacity="0.95"]'
    );
    await expect(visibleMapPaths).toHaveCount(2);

    await page
      .getByRole('button', { name: 'Use Remote diversion as estimated route' })
      .click();
    await expect(page.getByRole('alert')).toContainText('Planned route retained');
    await expect(page.getByRole('alert')).toContainText(
      'No feasible estimate (no_feasible_splice). The planned route and timeline remain in use.'
    );
    await expect.poll(() => unavailableRouteBasis).toBe('planned');
    await expect(
      page.getByText('Estimated map layer: derived estimate, not telemetry.')
    ).not.toBeVisible();
    await expect(visibleMapPaths).toHaveCount(0);
  });
});
