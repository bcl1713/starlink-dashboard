import { describe, expect, it } from 'vitest';

import type { OverviewGeometryPoint } from '../geometry';
import { buildFeatureBounds } from './operational-map-bounds';
import {
  buildOperationalFeatures,
  createHistoryIdRegistry,
} from './build-operational-features';
import type { OperationalFeature } from './operational-map-types';
import { makeOverviewSnapshot } from './test-fixtures';

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

  it('excludes synthetic IDL interpolation points from actual split route bounds', () => {
    const { features } = buildOperationalFeatures(
      makeOverviewSnapshot({
        routeWest: [
          { latitude: 10, longitude: 170 },
          { latitude: 12, longitude: -170 },
        ],
      }),
      createHistoryIdRegistry()
    );

    expect(
      buildFeatureBounds(
        features.filter((feature) => feature.layerId === 'planned-route-west')
      )
    ).toEqual([
      [10, 170],
      [12, 190],
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
