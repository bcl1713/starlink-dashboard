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

  it('assigns split ownership by largest timestamp overlap before display order', () => {
    const registry = createHistoryIdRegistry();
    const first = historyIds(registry, [
      ['2026-08-29T12:00:00Z', 10, -10],
      ['2026-08-29T12:00:01Z', 11, -11],
      ['2026-08-29T12:00:03Z', 13, -13],
      ['2026-08-29T12:00:04Z', 14, -14],
      ['2026-08-29T12:00:05Z', 15, -15],
    ]);
    const split = historyIds(registry, [
      ['2026-08-29T12:00:00Z', 10, -10],
      ['2026-08-29T12:00:01Z', 11, -11],
      ['2026-08-29T12:00:02Z', 12, 1],
      ['2026-08-29T12:00:03Z', 13, -13],
      ['2026-08-29T12:00:04Z', 14, -14],
      ['2026-08-29T12:00:05Z', 15, -15],
    ]);

    expect(first).toEqual(['history:west:1']);
    expect(split).toEqual(['history:west:2', 'history:west:1']);
  });

  it('assigns merge ownership by largest overlap and prior ID lexical tie', () => {
    const registry = createHistoryIdRegistry();
    historyIds(registry, [
      ['2026-08-29T12:00:00Z', 10, -10],
      ['2026-08-29T12:00:01Z', 11, -11],
      ['2026-08-29T12:00:02Z', 12, 1],
      ['2026-08-29T12:00:03Z', 13, -12],
      ['2026-08-29T12:00:04Z', 14, -13],
    ]);
    const merged = historyIds(registry, [
      ['2026-08-29T12:00:00Z', 10, -10],
      ['2026-08-29T12:00:01Z', 11, -11],
      ['2026-08-29T12:00:03Z', 13, -12],
      ['2026-08-29T12:00:04Z', 14, -13],
    ]);

    expect(merged).toEqual(['history:west:1']);
  });

  it('chooses global merge ownership independent of predecessor order', () => {
    const registry = createHistoryIdRegistry();
    historyIds(registry, [
      ['2026-08-29T12:00:00Z', 10, -10],
      ['2026-08-29T12:00:01Z', 11, -11],
      ['2026-08-29T12:00:02Z', 12, 1],
      ['2026-08-29T12:00:03Z', 13, -12],
      ['2026-08-29T12:00:04Z', 14, -13],
      ['2026-08-29T12:00:05Z', 15, -14],
    ]);
    const merged = historyIds(registry, [
      ['2026-08-29T12:00:01Z', 11, -11],
      ['2026-08-29T12:00:03Z', 13, -12],
      ['2026-08-29T12:00:04Z', 14, -13],
      ['2026-08-29T12:00:05Z', 15, -14],
    ]);

    expect(merged).toEqual(['history:west:2']);
  });

  it('does not render a history line for one real sample plus IDL boundary', () => {
    const registry = createHistoryIdRegistry();
    const features = buildOperationalFeatures(
      makeOverviewSnapshot({
        history: [
          ['2026-08-29T12:00:00Z', 10, 179],
          ['2026-08-29T12:00:10Z', 11, -179],
          ['2026-08-29T12:00:20Z', 12, -178],
        ],
      }),
      registry
    ).features.filter((feature) => feature.kind === 'history-segment');

    expect(features).toHaveLength(1);
    expect(features[0]?.layerId).toBe('position-history-west');
    expect(features[0]?.geometry.type === 'line').toBe(true);
    expect(
      features[0]?.geometry.type === 'line'
        ? features[0].geometry.sourcePoints?.map((point) => point.longitude)
        : []
    ).toEqual([-179, -178]);
  });

  it('renders only repeated IDL crossing runs with two real samples', () => {
    const registry = createHistoryIdRegistry();
    const features = buildOperationalFeatures(
      makeOverviewSnapshot({
        history: [
          ['2026-08-29T12:00:00Z', 10, 179],
          ['2026-08-29T12:00:10Z', 11, -179],
          ['2026-08-29T12:00:20Z', 12, -178],
          ['2026-08-29T12:00:30Z', 13, 178],
          ['2026-08-29T12:00:40Z', 14, 177],
        ],
      }),
      registry
    ).features.filter((feature) => feature.kind === 'history-segment');

    expect(features.map((feature) => feature.layerId)).toEqual([
      'position-history-west',
      'position-history-east',
    ]);
    expect(
      features.map((feature) =>
        feature.geometry.type === 'line'
          ? feature.geometry.sourcePoints?.map((point) => point.longitude)
          : []
      )
    ).toEqual([
      [-179, -178],
      [178, 177],
    ]);
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

function historyIds(
  registry: ReturnType<typeof createHistoryIdRegistry>,
  history: readonly (readonly [string, number, number])[]
): string[] {
  return buildOperationalFeatures(makeOverviewSnapshot({ history }), registry)
    .features.filter((feature) => feature.kind === 'history-segment')
    .map((feature) => feature.id);
}
