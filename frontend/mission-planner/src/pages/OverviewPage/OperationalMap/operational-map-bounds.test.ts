import { describe, expect, it } from 'vitest';

import type { OverviewGeometryPoint } from '../geometry';
import { buildFeatureBounds } from './operational-map-bounds';
import type { OperationalFeature } from './operational-map-types';

describe('operational map bounds', () => {
  it('uses the minimal circular longitude interval across the date line', () => {
    const bounds = buildFeatureBounds([
      line('route:west:pacific:0', [
        { latitude: 10, longitude: 170, altitudeMeters: null, timestamp: null },
        {
          latitude: 12,
          longitude: -170,
          altitudeMeters: null,
          timestamp: null,
        },
      ]),
    ]);

    expect(bounds).toEqual([
      [10, 170],
      [12, 190],
    ]);
  });

  it('rejects invalid point candidates instead of expanding fit bounds', () => {
    const bounds = buildFeatureBounds([
      {
        id: 'bad',
        layerId: 'current-position-layer',
        kind: 'current-position',
        label: 'Bad point',
        geometry: { type: 'point', latitude: 95, longitude: 500 },
        details: [],
      },
      line('ok', [
        { latitude: 1, longitude: 2, altitudeMeters: null, timestamp: null },
        { latitude: 3, longitude: 4, altitudeMeters: null, timestamp: null },
      ]),
    ]);

    expect(bounds).toEqual([
      [1, 2],
      [3, 4],
    ]);
  });
});

function line(
  id: string,
  points: readonly OverviewGeometryPoint[]
): OperationalFeature {
  return {
    id,
    layerId: 'planned-route-west',
    kind: 'route-segment',
    label: id,
    geometry: { type: 'line', points },
    details: [],
  };
}
