import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getRouteCoordinates } from './monitoring';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);
const aware = '2026-08-29T12:34:56Z';
const coordinate = {
  latitude: 39,
  longitude: -104,
  altitude_meters: null,
  sequence: 1.5,
};
const payload = {
  route_id: 'route-1',
  route_name: null,
  revision_at: '2026-08-29T12:00:00+00:00',
  generated_at: aware,
  total: 1,
  coordinates: [coordinate],
};

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce({ data });
}

describe('route coordinates overview service', () => {
  it('requests exact directional endpoints and preserves revision/generated timestamps', async () => {
    const signal = new AbortController().signal;
    respond(payload);

    await expect(getRouteCoordinates('west', signal)).resolves.toEqual(payload);
    expect(getMock).toHaveBeenCalledWith('/api/route/coordinates/west', {
      signal,
    });

    const named = { ...payload, route_name: 'Westbound', revision_at: null };
    respond(named);
    await expect(getRouteCoordinates('east')).resolves.toEqual(named);
    expect(getMock).toHaveBeenLastCalledWith('/api/route/coordinates/east', {
      signal: undefined,
    });
  });

  it('rejects malformed route contracts', async () => {
    const invalid = [
      { ...payload, total: 2 },
      { ...payload, total: 1.5 },
      { ...payload, route_id: 123 },
      { ...payload, route_name: 123 },
      { ...payload, revision_at: '2026-08-29T12:00:00' },
      { ...payload, generated_at: '2026-08-29T12:34:56' },
      { ...payload, extra: true },
      { ...payload, coordinates: [{ ...coordinate, latitude: -91 }] },
      { ...payload, coordinates: [{ ...coordinate, longitude: 181 }] },
      {
        ...payload,
        coordinates: [{ ...coordinate, altitude_meters: Infinity }],
      },
      { ...payload, coordinates: [{ ...coordinate, sequence: NaN }] },
      { ...payload, coordinates: [{ ...coordinate, x: 1 }] },
    ];

    for (const bad of invalid) {
      respond(bad);
      await expect(getRouteCoordinates('west')).rejects.toMatchObject({
        source: 'route-coordinates',
      });
    }
  });
});
