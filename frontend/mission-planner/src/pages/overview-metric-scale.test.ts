import { describe, expect, it } from 'vitest';
import {
  OVERVIEW_METRIC_GRAPHS,
  type ProjectedMetricHistory,
} from './overview-metric-history';
import { metricScale } from './overview-metric-scale';
const projection = (
  values: (number | null)[],
  high = values
): ProjectedMetricHistory => ({
  state: 'available',
  times: [],
  observed: values,
  min: [0],
  avg: values,
  max: high,
  visibleRightSeconds: 0,
});
describe('metricScale', () => {
  it.each([
    [1.2, 1.4],
    [3, 3.3],
    [6, 6.6],
  ])(
    'normalizes fractional loss peak %s to readable domain %s',
    (peak, upper) => {
      expect(
        metricScale(OVERVIEW_METRIC_GRAPHS[3], projection([peak]))
      ).toEqual({ min: 0, max: upper });
    }
  );
  it('keeps obstruction on its full percentage domain', () => {
    expect(metricScale(OVERVIEW_METRIC_GRAPHS[4], projection([0.2]))).toEqual({
      min: 0,
      max: 100,
    });
  });
  it('makes 0.2 percent loss distinguishable with a labelled one percent upper bound', () => {
    expect(metricScale(OVERVIEW_METRIC_GRAPHS[3], projection([0.2]))).toEqual({
      min: 0,
      max: 1,
    });
    expect(metricScale(OVERVIEW_METRIC_GRAPHS[3], projection([2]))).toEqual({
      min: 0,
      max: 2.2,
    });
  });
  it.each(OVERVIEW_METRIC_GRAPHS.slice(0, 3))(
    'includes aggregate highs with rounded headroom for $id',
    (descriptor) => {
      expect(metricScale(descriptor, projection([7], [20]))).toEqual({
        min: 0,
        max: 22,
      });
    }
  );
  it('retains the domain through small oscillations but expands immediately past it', () => {
    const descriptor = OVERVIEW_METRIC_GRAPHS[0];
    expect(
      metricScale(descriptor, projection([19]), { min: 0, max: 22 })
    ).toEqual({ min: 0, max: 22 });
    expect(
      metricScale(descriptor, projection([21]), { min: 0, max: 22 })
    ).toEqual({ min: 0, max: 22 });
    expect(
      metricScale(descriptor, projection([23]), { min: 0, max: 22 })
    ).toEqual({ min: 0, max: 26 });
  });
  it.each(
    [[], [0], [null, NaN, Infinity], [Number.MAX_VALUE]].map((values) => [
      values,
    ])
  )('returns finite nondegenerate bounds for %j', (values) => {
    const range = metricScale(OVERVIEW_METRIC_GRAPHS[0], projection(values));
    expect(range.min).toBe(0);
    expect(Number.isFinite(range.max)).toBe(true);
    expect(range.max).toBeGreaterThan(0);
    for (const value of values)
      if (typeof value === 'number' && Number.isFinite(value))
        expect(range.max).toBeGreaterThanOrEqual(value);
  });
});
