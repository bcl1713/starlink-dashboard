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
  it.each(OVERVIEW_METRIC_GRAPHS.slice(3))(
    'fixes $id at 0–100 regardless of samples or prior range',
    (descriptor) => {
      for (const values of [[], [0], [0.2], [100], [120], [null, NaN]])
        expect(
          metricScale(descriptor, projection(values), { min: 0, max: 1 })
        ).toEqual({ min: 0, max: 100 });
      expect(metricScale(descriptor, undefined)).toEqual({ min: 0, max: 100 });
    }
  );
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
  it.each(OVERVIEW_METRIC_GRAPHS.slice(0, 3))(
    'shrinks $id after a large peak leaves without jitter near the bound',
    (descriptor) => {
      expect(
        metricScale(descriptor, projection([50]), { min: 0, max: 220 })
      ).toEqual({ min: 0, max: 56 });
      expect(
        metricScale(descriptor, projection([40]), { min: 0, max: 56 })
      ).toEqual({ min: 0, max: 56 });
    }
  );
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
