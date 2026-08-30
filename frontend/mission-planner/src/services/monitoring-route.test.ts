import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './api-client';
import { getRouteCoordinates } from './monitoring';
import {
  routeCoordinate,
  routePayload,
  setAt,
  withResponse,
} from './monitoring-test-fixtures';

vi.mock('./api-client', () => ({ apiClient: { get: vi.fn() } }));

const getMock = vi.mocked(apiClient.get);

beforeEach(() => getMock.mockReset());

function respond(data: unknown) {
  getMock.mockResolvedValueOnce(withResponse(data));
}

async function expectRouteInvalid(payload: unknown) {
  respond(payload);
  await expect(getRouteCoordinates('west')).rejects.toMatchObject({
    source: 'route-coordinates',
  });
}

describe('route coordinates overview service', () => {
  it('requests exact directional endpoints and parses nullable ids/names', async () => {
    const signal = new AbortController().signal;
    respond(routePayload);
    await expect(getRouteCoordinates('west', signal)).resolves.toEqual(
      routePayload
    );
    expect(getMock).toHaveBeenCalledWith('/api/route/coordinates/west', {
      signal,
    });

    const nullable = {
      ...routePayload,
      route_id: null,
      route_name: null,
      revision_at: null,
    };
    respond(nullable);
    await expect(getRouteCoordinates('east')).resolves.toEqual(nullable);
    expect(getMock).toHaveBeenLastCalledWith('/api/route/coordinates/east', {
      signal: undefined,
    });
  });

  it('accepts fractional sequence and finite altitude variants', async () => {
    const payload = {
      ...routePayload,
      coordinates: [
        { ...routeCoordinate, altitude_meters: -20, sequence: 1.5 },
      ],
    };
    respond(payload);
    await expect(getRouteCoordinates('west')).resolves.toEqual(payload);
  });

  it('rejects malformed route contracts by isolated mutation', async () => {
    const invalid = [
      setAt(routePayload, ['total'], -1),
      setAt(routePayload, ['total'], 2),
      setAt(routePayload, ['total'], 1.5),
      setAt(routePayload, ['total'], '1'),
      setAt(routePayload, ['route_id'], 123),
      setAt(routePayload, ['route_name'], 123),
      setAt(routePayload, ['revision_at'], '2026-08-29T12:00:00'),
      setAt(routePayload, ['generated_at'], '2026-08-29T12:34:56'),
      setAt(routePayload, ['extra'], true),
      setAt(routePayload, ['coordinates', 0, 'latitude'], -91),
      setAt(routePayload, ['coordinates', 0, 'latitude'], 91),
      setAt(routePayload, ['coordinates', 0, 'latitude'], NaN),
      setAt(routePayload, ['coordinates', 0, 'latitude'], '39'),
      setAt(routePayload, ['coordinates', 0, 'longitude'], -181),
      setAt(routePayload, ['coordinates', 0, 'longitude'], 181),
      setAt(routePayload, ['coordinates', 0, 'longitude'], Infinity),
      setAt(routePayload, ['coordinates', 0, 'longitude'], '-104'),
      setAt(routePayload, ['coordinates', 0, 'altitude_meters'], Infinity),
      setAt(routePayload, ['coordinates', 0, 'altitude_meters'], '1'),
      setAt(routePayload, ['coordinates', 0, 'sequence'], NaN),
      setAt(routePayload, ['coordinates', 0, 'sequence'], '1'),
      setAt(routePayload, ['coordinates', 0, 'x'], 1),
    ];

    for (const bad of invalid) await expectRouteInvalid(bad);
  });
});
