import { expect, test } from '@playwright/test';
import { seedOverviewWindowMission } from './support/overview-window-mission';

// Real API, persistence, Nginx and browser rendering; no intercepted API data.
test('AR boundaries render and each POI event layer can be toggled independently', async ({
  context,
  request,
}, info) => {
  expect(process.env.ACCEPTANCE_CANDIDATE_SHA).toMatch(/^[a-f0-9]{40}$/);
  const seed = await seedOverviewWindowMission(request);
  const mission = await (
    await request.get(`/api/v2/missions/${seed.missionId}`)
  ).json();
  const leg = mission.legs.find(
    (row: { id: string }) => row.id === seed.firstLegId
  );
  const start = Date.parse(leg.adjusted_departure_time);
  const at = (minutes: number) =>
    new Date(start + minutes * 60000).toISOString();
  const endpoint = '/api/overview-links/settings';
  const initial = await (await request.get(endpoint)).json();
  const editing = await context.newPage();
  const overview = await context.newPage();
  try {
    const updated = await request.put(
      `/api/v2/missions/${seed.missionId}/legs/${seed.firstLegId}`,
      {
        data: {
          transports: {
            ...leg.transports,
            aar_windows: [
              {
                id: 'ar-window',
                start_waypoint_name: 'KAAA',
                end_waypoint_name: 'KBBB',
                override_start_time: at(20),
                override_end_time: at(40),
              },
            ],
            manual_aar_tracks: [
              {
                id: 'manual-ar',
                name: 'Manual refuel',
                points: [
                  { latitude: 35.06, longitude: -99.94 },
                  { latitude: 35.07, longitude: -99.93 },
                ],
              },
            ],
            x_transitions: [
              {
                id: 'swap',
                latitude: 35.04,
                longitude: -99.96,
                target_satellite_id: 'X-1',
              },
            ],
            ka_outages: [
              { id: 'ka-loss', start_time: at(80), duration_seconds: 600 },
            ],
            ku_overrides: [
              {
                id: 'starshield-loss',
                start_time: at(60),
                duration_seconds: 600,
                reason: 'Acceptance outage',
              },
            ],
          },
        },
      }
    );
    expect(updated.status(), await updated.text()).toBe(200);
    const activated = await request.post(
      `/api/v2/missions/${seed.missionId}/legs/${seed.firstLegId}/activate`
    );
    expect(activated.status(), await activated.text()).toBe(200);
    const response = await request.get('/api/overview/upcoming-pois');
    expect(response.status()).toBe(200);
    const pois: Array<{ kind: string; name: string; map_retained: boolean }> = (
      await response.json()
    ).pois;
    const visible = pois.filter((p) => p.map_retained);
    expect(pois.filter((p) => p.kind === 'aar_start')).toHaveLength(2);
    expect(pois.filter((p) => p.kind === 'aar_end')).toHaveLength(2);
    expect(pois.some((p) => p.kind === 'starshield_outage_start')).toBe(true);
    await overview.goto('/overview');
    await expect(overview.locator('.overview-globe canvas')).toBeVisible();
    const names = overview
      .getByRole('list', { name: 'Map POIs' })
      .getByRole('listitem');
    await expect(names).toHaveCount(visible.length);
    await editing.goto('/configuration');
    const groups = [
      {
        label: 'Flight events',
        field: 'flight_events_enabled',
        kinds: ['departure', 'arrival', 'aar_start', 'aar_end'],
      },
      {
        label: 'X-band events',
        field: 'x_band_events_enabled',
        kinds: [
          'x_band_transition',
          'x_band_warning_start',
          'x_band_warning_end',
        ],
      },
      {
        label: 'Ka-band events',
        field: 'ka_events_enabled',
        kinds: [
          'ka_transition',
          'ka_coverage_exit',
          'ka_coverage_entry',
          'ka_outage_start',
          'ka_outage_end',
        ],
      },
      {
        label: 'Starshield events',
        field: 'starshield_events_enabled',
        kinds: ['starshield_outage_start', 'starshield_outage_end'],
      },
    ];
    for (const group of groups) {
      const control = editing.getByRole('switch', {
        name: group.label,
        exact: true,
      });
      await expect(control).toBeChecked();
      await control.uncheck();
      await expect
        .poll(
          async () => (await (await request.get(endpoint)).json())[group.field]
        )
        .toBe(false);
      await expect(names).toHaveCount(
        visible.filter((p) => !group.kinds.includes(p.kind)).length
      );
      await control.check();
      await expect(names).toHaveCount(visible.length);
    }
    await overview.screenshot({
      path: info.outputPath('overview-event-pois.png'),
    });
    await editing.goto(`/missions/${seed.missionId}/legs/${seed.firstLegId}`);
    const arMarkers = editing.locator('.leaflet-marker-icon[title="AR Start"]');
    await expect(arMarkers).toHaveCount(2);
    const flight = editing.getByRole('checkbox', {
      name: 'Flight events',
      exact: true,
    });
    await flight.uncheck();
    await expect(arMarkers).toHaveCount(0);
    await expect(
      editing.locator('.leaflet-marker-icon[title="Starshield Loss"]')
    ).toHaveCount(1);
    await flight.check();
    await expect(arMarkers).toHaveCount(2);
    await editing.screenshot({ path: info.outputPath('route-event-pois.png') });
    await info.attach('generated-pois.json', {
      body: JSON.stringify(pois, null, 2),
      contentType: 'application/json',
    });
  } finally {
    await overview.close();
    await editing.close();
    await request.put(endpoint, { data: initial });
    await request.post(`/api/v2/missions/${seed.missionId}/legs/deactivate`);
    await request.delete(`/api/v2/missions/${seed.missionId}`);
  }
});
