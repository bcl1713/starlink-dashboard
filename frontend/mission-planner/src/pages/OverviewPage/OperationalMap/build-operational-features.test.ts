import { describe, expect, it } from 'vitest';

import {
  buildOperationalFeatures,
  createHistoryIdRegistry,
} from './build-operational-features';
import { makeOverviewSnapshot } from './test-fixtures';

describe('operational feature building', () => {
  it('splits route and active link sources without cross-boundary lines', () => {
    const snapshot = makeOverviewSnapshot({
      routeWest: [
        { latitude: 10, longitude: 170 },
        { latitude: 10, longitude: -170 },
      ],
      activeNormal: [
        { latitude: 20, longitude: -120 },
        { latitude: 21, longitude: -119 },
      ],
    });
    const output = buildOperationalFeatures(
      snapshot,
      createHistoryIdRegistry()
    );

    expect(
      output.features
        .filter((feature) => feature.layerId === 'planned-route-west')
        .map((feature) => feature.id)
    ).toEqual(['route:west:route-west:0', 'route:west:route-west:1']);
    expect(
      output.features
        .filter((feature) => feature.layerId === 'active-x-band-normal')
        .map((feature) => feature.id)
    ).toEqual(['active-link:normal:sat-a:0']);
  });

  it('keeps history feature IDs through rolling-window eviction', () => {
    const registry = createHistoryIdRegistry();
    const first = buildOperationalFeatures(
      makeOverviewSnapshot({
        history: [
          ['2026-08-29T12:00:00Z', 10, -10],
          ['2026-08-29T12:00:01Z', 11, -11],
          ['2026-08-29T12:00:02Z', 12, 10],
          ['2026-08-29T12:00:03Z', 13, 11],
        ],
      }),
      registry
    ).features.filter((feature) => feature.kind === 'history-segment');
    const second = buildOperationalFeatures(
      makeOverviewSnapshot({
        history: [
          ['2026-08-29T12:00:02Z', 12, 10],
          ['2026-08-29T12:00:03Z', 13, 11],
          ['2026-08-29T12:00:04Z', 14, 12],
        ],
      }),
      registry
    ).features.filter((feature) => feature.kind === 'history-segment');

    expect(first.map((feature) => feature.id)).toEqual([
      'history:west:1',
      'history:east:2',
    ]);
    expect(second.map((feature) => feature.id)).toEqual(['history:east:2']);
  });

  it('derives retained last-good source state from non-ready slots with data', () => {
    const output = buildOperationalFeatures(
      makeOverviewSnapshot({ routePhase: 'error', routeError: true }),
      createHistoryIdRegistry()
    );

    expect(
      output.layerStates.find((state) => state.id === 'planned-route-west')
    ).toMatchObject({
      phase: 'error',
      retainedLastGood: true,
      message: 'Source refresh failed. Showing retained last-good data.',
    });
  });
});
