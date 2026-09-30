import { describe, expect, it } from 'vitest';
import type {
  OverviewHistoryBundle,
  OverviewHistorySample,
} from '../services/overview-history';
import {
  OVERVIEW_METRIC_GRAPHS,
  projectMetricHistory,
} from './overview-metric-history';
import { retainMetricHistory } from './overview-metric-retention';

const descriptor = OVERVIEW_METRIC_GRAPHS[0];
const metric = descriptor.metric;
const edge = 10204;
const traces = ['observed', 'min', 'avg', 'max'] as const;
type Trace = (typeof traces)[number];

function response(
  end: number,
  points: Partial<Record<Trace, OverviewHistorySample[]>>,
  options: { window?: number; state?: 'available' | 'unavailable' } = {}
): OverviewHistoryBundle {
  return {
    window_seconds: options.window ?? 1800,
    start_timestamp_seconds: end - (options.window ?? 1800),
    end_timestamp_seconds: end,
    step_seconds: 1,
    series: { [metric]: points.observed ?? [] },
    rolling_5m: {
      [metric]: {
        state: options.state ?? 'available',
        min: points.min ?? [],
        avg: points.avg ?? [],
        max: points.max ?? [],
      },
    },
  };
}
const point = (time: number, value: number): OverviewHistorySample => [
  time,
  value,
];
function values(bundle: OverviewHistoryBundle) {
  const plotted = projectMetricHistory(
    bundle,
    descriptor,
    bundle.end_timestamp_seconds * 1000
  );
  return Object.fromEntries(
    traces.map((trace) => [
      trace,
      plotted.times.flatMap((time, index) =>
        plotted[trace][index] === null ? [] : [[time, plotted[trace][index]]]
      ),
    ])
  );
}

describe('chart-only real-sample retention', () => {
  it('keeps each independent trace across two rebases until it exits the viewport', () => {
    let cache = retainMetricHistory(
      undefined,
      response(12000, {
        observed: [point(edge, 11)],
        min: [point(edge, 12)],
        avg: [point(edge, 13)],
        max: [point(edge, 14)],
      }),
      descriptor
    );
    for (const end of [12005, 12010]) {
      cache = retainMetricHistory(cache, response(end, {}), descriptor);
      for (const [index, trace] of traces.entries())
        expect(values(cache.bundle)[trace]).toContainEqual([edge, 11 + index]);
    }
    cache = retainMetricHistory(cache, response(12012, {}), descriptor);
    for (const trace of traces) expect(values(cache.bundle)[trace]).toEqual([]);
  });

  it('uses newer overlapping revisions and deletions, without restoring unavailable aggregates', () => {
    let cache = retainMetricHistory(
      undefined,
      response(12000, {
        observed: [point(10205, 1), point(10206, 2)],
        min: [point(10205, 3)],
        avg: [point(10205, 4)],
        max: [point(10205, 5)],
      }),
      descriptor
    );
    cache = retainMetricHistory(
      cache,
      response(12005, {
        observed: [point(10205, 9)],
        min: [point(10205, 8)],
      }),
      descriptor
    );
    expect(values(cache.bundle)).toEqual({
      observed: [[10205, 9]],
      min: [[10205, 8]],
      avg: [],
      max: [],
    });
    cache = retainMetricHistory(
      cache,
      response(
        12010,
        {
          observed: [point(10210, 7)],
        },
        { state: 'unavailable' }
      ),
      descriptor
    );
    expect(projectMetricHistory(cache.bundle, descriptor, 12010000).state).toBe(
      'unavailable'
    );
    expect(values(cache.bundle)).toEqual({
      observed: [
        [10205, 9],
        [10210, 7],
      ],
      min: [],
      avg: [],
      max: [],
    });
  });

  it('does not connect points over a missed poll or cache synthetic gap markers', () => {
    let cache = retainMetricHistory(
      undefined,
      response(12000, {
        observed: [point(edge, 4)],
      }),
      descriptor
    );
    cache = retainMetricHistory(
      cache,
      response(12010, {
        observed: [point(10210, 7)],
      }),
      descriptor
    );
    const plotted = projectMetricHistory(cache.bundle, descriptor, 12010000);
    expect(plotted.times).toEqual([10204, 10207, 10210]);
    expect(plotted.observed).toEqual([4, null, 7]);
    expect(cache.bundle.series[metric]).toEqual([
      point(edge, 4),
      point(10210, 7),
    ]);
    cache = retainMetricHistory(
      cache,
      response(12020, {
        observed: [point(10220, 7)],
      }),
      descriptor
    );
    expect(
      projectMetricHistory(cache.bundle, descriptor, 12020000).times
    ).toEqual([10220]);
    cache = retainMetricHistory(
      cache,
      response(12021, {
        observed: [point(10221, 8)],
      }),
      descriptor
    );
    expect(cache.bundle.series[metric]).toEqual([
      point(10220, 7),
      point(10221, 8),
    ]);
  });

  it('rejects older bundles and clears on a window change', () => {
    let cache = retainMetricHistory(
      undefined,
      response(12000, {
        observed: [point(edge, 4)],
      }),
      descriptor
    );
    cache = retainMetricHistory(cache, response(12005, {}), descriptor);
    const older = retainMetricHistory(
      cache,
      response(12001, {
        observed: [point(10205, 99)],
      }),
      descriptor
    );
    expect(older).toBe(cache);
    cache = retainMetricHistory(
      cache,
      response(12010, {}, { window: 900 }),
      descriptor
    );
    expect(values(cache.bundle).observed).toEqual([]);
  });

  it('bounds retained points through many accepted refreshes', () => {
    let cache = retainMetricHistory(
      undefined,
      response(12000, {
        observed: Array.from({ length: 1801 }, (_, i) => point(10200 + i, i)),
      }),
      descriptor
    );
    for (let end = 12005; end <= 13000; end += 5)
      cache = retainMetricHistory(
        cache,
        response(end, {
          observed: Array.from({ length: 1801 }, (_, i) =>
            point(end - 1800 + i, i)
          ),
        }),
        descriptor
      );
    expect(cache.bundle.series[metric].length).toBeLessThanOrEqual(1820);
    expect(cache.bundle.series[metric][0][0]).toBeGreaterThanOrEqual(
      13000 - 1800 - 7.5
    );
  });
});
