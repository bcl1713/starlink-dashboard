import { readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { expect, type APIRequestContext } from '@playwright/test';

/** Real V2 storage contract, matching the tracked activation integration asset. */
export async function seedOverviewWindowMission(request: APIRequestContext) {
  const missionId = `window-${randomUUID()}`;
  const firstLegId = `first-${randomUUID()}`;
  const secondLegId = `second-${randomUUID()}`;
  const created = await request.post('/api/v2/missions', {
    data: { id: missionId, name: 'Overview window acceptance', legs: [] },
  });
  expect(created.status(), await created.text()).toBe(201);
  const kml = await readFile(
    new URL(
      '../../../../../docs/missions/acceptance-assets/v2-activation-route.kml',
      import.meta.url
    ),
    'utf8'
  );
  const secondKml = kml
    .replaceAll('KAAA', 'KCCC')
    .replaceAll('KBBB', 'KDDD')
    .replace(
      /(-?\d+\.\d+),(-?\d+\.\d+),(\d+)/g,
      (_match, lon, lat, altitude) =>
        `${(Number(lon) + 10).toFixed(4)},${(Number(lat) + 2).toFixed(4)},${altitude}`
    );
  const routeIds: string[] = [];
  for (const [index, legId] of [firstLegId, secondLegId].entries()) {
    const added = await request.post(`/api/v2/missions/${missionId}/legs`, {
      data: {
        id: legId,
        name: index === 0 ? 'First leg' : 'Second leg',
        route_id: `pending-${legId}`,
        transports: {
          initial_x_satellite_id: 'X-1',
          initial_ka_satellite_ids: ['AOR'],
        },
        adjusted_departure_time: new Date(Date.now() + 3600000).toISOString(),
      },
    });
    expect(added.status(), await added.text()).toBe(201);
    const uploaded = await request.put(
      `/api/v2/missions/${missionId}/legs/${legId}/route`,
      {
        multipart: {
          file: {
            name: index === 0 ? 'first.kml' : 'second.kml',
            mimeType: 'application/vnd.google-earth.kml+xml',
            buffer: Buffer.from(index === 0 ? kml : secondKml),
          },
        },
      }
    );
    expect(uploaded.status(), await uploaded.text()).toBe(200);
    const result = await uploaded.json();
    expect(result.leg.id).toBe(legId);
    expect(result.leg.route_id).toEqual(expect.any(String));
    routeIds.push(result.leg.route_id);
  }
  return {
    missionId,
    firstLegId,
    secondLegId,
    firstRouteId: routeIds[0],
    secondRouteId: routeIds[1],
  };
}
