import {
  expect,
  type APIRequestContext,
  type APIResponse,
} from '@playwright/test';
import { randomUUID } from 'node:crypto';
import type { EventSnapshot } from '../../src/types/operatorEvents';
const catalog =
  '/app/data/operator/transport-availability/availability-pops.json';
export async function json<T = Record<string, unknown>>(
  response: APIResponse
): Promise<T> {
  expect(response.ok(), `${response.status()} ${await response.text()}`).toBe(
    true
  );
  return response.json();
}
export async function raw(request: APIRequestContext, elapsed = 1764) {
  return json<{ departure: string }>(
    await request.post('/api/_synthetic/transport-inputs', {
      data: { elapsed_seconds: elapsed },
    })
  );
}
export async function seed(request: APIRequestContext) {
  const { departure } = await raw(request, 0);
  const at = (minute: number) =>
    new Date(Date.parse(departure) + minute * 60_000).toISOString();
  const missionId = `overview-${randomUUID()}`;
  await json(
    await request.post('/api/pois', {
      data: {
        name: 'Overview-X-1',
        latitude: 0,
        longitude: 90,
        category: 'satellite',
      },
    })
  );
  await json(
    await request.post('/api/v2/missions', {
      data: { id: missionId, name: 'Synthetic Overview Acceptance', legs: [] },
    })
  );
  const legs = [];
  for (const n of [1, 2]) {
    const leg = `overview-leg-${n}`;
    await json(
      await request.post(`/api/v2/missions/${missionId}/legs`, {
        data: {
          id: leg,
          name: `Synthetic Leg ${n}`,
          route_id: `pending-${n}`,
          adjusted_departure_time: departure,
          transports: {
            initial_x_satellite_id: 'Overview-X-1',
            initial_ka_satellite_ids: ['AOR'],
            starshield_enabled: true,
            ka_outages: [
              { id: `ka-${n}`, start_time: at(29), duration_seconds: 180 },
            ],
            ku_overrides: [
              { id: `ku-${n}`, start_time: at(29), duration_seconds: 180 },
            ],
            aar_windows: [
              {
                id: `ar-${n}`,
                start_waypoint_name: 'AR IN',
                end_waypoint_name: 'AR OUT',
              },
            ],
          },
        },
      })
    );
    const points: [string, number, number][] = [
      ['Departure', -10, 0],
      ['Middle', 0, 30],
      ['AR IN', 1, 33],
      ['AR OUT', 2, 36],
      ['Arrival', 10, 60],
    ];
    const placemarks = points
      .map(
        ([name, lon, minute]) =>
          `<Placemark><name>${name}</name><description>Time Over Waypoint: ${at(minute).replace('T', ' ').replace('.000Z', 'Z')}</description><Point><coordinates>${lon},0,10000</coordinates></Point></Placemark>`
      )
      .join('');
    const kml = `<kml xmlns="http://www.opengis.net/kml/2.2"><Document>${placemarks}<Placemark><LineString><coordinates>${points.map(([, lon]) => `${lon},0,10000`).join(' ')}</coordinates></LineString></Placemark></Document></kml>`;
    await json(
      await request.put(`/api/v2/missions/${missionId}/legs/${leg}/route`, {
        multipart: {
          file: {
            name: `overview-${n}.kml`,
            mimeType: 'application/vnd.google-earth.kml+xml',
            buffer: Buffer.from(kml),
          },
        },
      })
    );
    legs.push(leg);
  }
  const config = await json<
    Record<string, unknown> & { pop: Record<string, unknown> }
  >(await request.get('/api/config'));
  await json(
    await request.post('/api/config', {
      data: {
        ...config,
        mode: 'live',
        pop: { ...config.pop, catalog_path: catalog },
      },
    })
  );
  const activate = async (leg: string, elapsed = 1764) => {
    await json(
      await request.post(`/api/v2/missions/${missionId}/legs/${leg}/activate`)
    );
    await json(
      await request.post('/api/flight-status/depart', {
        data: {
          timestamp: departure,
          reason: 'Synthetic raw flight-state input',
        },
      })
    );
    await raw(request, elapsed);
  };
  await activate(legs[0]);
  return { missionId, legs, activate };
}
export async function feed(request: APIRequestContext, missionId: string) {
  return json<EventSnapshot>(
    await request.get(
      `/api/v2/operator/events?mission_id=${missionId}&include_history=true`
    )
  );
}
