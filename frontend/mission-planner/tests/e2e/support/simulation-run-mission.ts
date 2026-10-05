import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { expect, type APIRequestContext } from '@playwright/test';

/** 12 safety + 2 AAR + 4 outage + 3 pre-arrival X events (4 on the long route). */
export async function seedSimulationRunMission(
  request: APIRequestContext,
  long = false
) {
  const missionId = `paced-${randomUUID()}`,
    legId = `leg-${randomUUID()}`;
  const departure = '2025-01-01T01:00:00Z';
  const existing = await request.get('/api/v2/missions');
  expect(existing.ok()).toBeTruthy();
  for (const mission of await existing.json()) {
    if (mission.legs.some((leg: { is_active: boolean }) => leg.is_active)) {
      expect(
        (
          await request.post(`/api/v2/missions/${mission.id}/legs/deactivate`)
        ).ok()
      ).toBeTruthy();
    }
  }
  const pois = await (await request.get('/api/pois')).json();
  for (const [index, longitude] of [175, 177, 179].entries()) {
    const name = `Paced-X-${index + 1}`;
    if (!pois.pois?.some((poi: { name: string }) => poi.name === name)) {
      const created = await request.post('/api/pois', {
        data: { name, latitude: 0, longitude, category: 'satellite' },
      });
      expect(created.ok(), await created.text()).toBeTruthy();
    }
  }
  expect(
    (
      await request.post('/api/v2/missions', {
        data: { id: missionId, name: 'Paced acceptance mission', legs: [] },
      })
    ).status()
  ).toBe(201);
  const at = (seconds: number) =>
    new Date(Date.parse(departure) + seconds * 1000).toISOString();
  const scale = long ? 10 : 1;
  const added = await request.post(`/api/v2/missions/${missionId}/legs`, {
    data: {
      id: legId,
      name: 'Timed dateline leg',
      route_id: `pending-${legId}`,
      adjusted_departure_time: departure,
      transports: {
        initial_x_satellite_id: 'Paced-X-1',
        initial_ka_satellite_ids: ['PAC'],
        x_transitions: [
          {
            id: 'first',
            latitude: 35,
            longitude: 180,
            target_satellite_id: 'Paced-X-2',
          },
          {
            id: 'second',
            latitude: 35,
            longitude: -179.5,
            target_satellite_id: 'Paced-X-3',
          },
        ],
        aar_windows: [
          {
            id: 'aar',
            start_waypoint_name: 'AAR Start',
            end_waypoint_name: 'AAR End',
          },
        ],
        ka_outages: [
          {
            id: 'ka',
            start_time: at(120 * scale),
            duration_seconds: 600 * scale,
          },
        ],
        ku_overrides: [
          {
            id: 'ku',
            start_time: at(120 * scale),
            duration_seconds: 600 * scale,
          },
        ],
      },
    },
  });
  expect(added.status(), await added.text()).toBe(201);
  let kml = await readFile(
    new URL(
      '../../../../../docs/missions/acceptance-assets/paced-simulation-route.kml',
      import.meta.url
    ),
    'utf8'
  );
  if (long)
    kml = kml
      .replace('00:05:00Z', '00:50:00Z')
      .replace('00:15:00Z', '02:30:00Z')
      .replace('00:20:00Z', '03:20:00Z');
  const uploaded = await request.put(
    `/api/v2/missions/${missionId}/legs/${legId}/route`,
    {
      multipart: {
        file: {
          name: 'paced.kml',
          mimeType: 'application/vnd.google-earth.kml+xml',
          buffer: Buffer.from(kml),
        },
      },
    }
  );
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
  const leg = (await uploaded.json()).leg;
  return {
    missionId,
    legId,
    routeId: leg.route_id as string,
    expectedEventCount: long ? 22 : 21,
    arrival: { latitude: 35, longitude: -179 },
    expectedFinalStates: { X: 'offline', Ka: 'offline', Ku: 'offline' },
    departure,
    duration: 1200 * scale,
  };
}
export async function startSimulation(
  request: APIRequestContext,
  seed: Awaited<ReturnType<typeof seedSimulationRunMission>>,
  pacing:
    | { mode: 'multiplier'; multiplier: number }
    | { mode: 'target_runtime'; runtime_seconds: number }
) {
  const path = `/api/v2/missions/${seed.missionId}/legs/${seed.legId}`;
  const response = await request.post(`${path}/simulation/preview`, {
    data: pacing,
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const preview = await response.json();
  const start = await request.post(`${path}/activate`, {
    data: { simulation: { pacing, plan_token: preview.plan_token } },
  });
  expect(start.ok(), await start.text()).toBeTruthy();
  return (await start.json()).simulation_run;
}
