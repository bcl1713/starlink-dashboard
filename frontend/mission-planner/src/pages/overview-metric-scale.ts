import type {
  OverviewMetricGraphDescriptor,
  ProjectedMetricTraces,
} from './overview-metric-history';

export interface YRange {
  min: number;
  max: number;
}

// Percentages below 1 share the baseline on logarithmic plots.
export const PERCENT_LOG_FLOOR = 1;

export function isLogarithmicMetric(
  descriptor: OverviewMetricGraphDescriptor
): boolean {
  return descriptor.id === 'obstruction' || descriptor.id === 'packet-loss';
}

/** Fixed logarithmic percentages; linear metrics use rounded headroom and hysteresis. */
export function metricScale(
  descriptor: OverviewMetricGraphDescriptor,
  projected: ProjectedMetricTraces | undefined,
  previous?: YRange
): YRange {
  if (isLogarithmicMetric(descriptor))
    return { min: PERCENT_LOG_FLOOR, max: 100 };
  let peak = 0;
  for (const trace of projected
    ? [projected.observed, projected.min, projected.avg, projected.max]
    : []) {
    for (const value of trace)
      if (typeof value === 'number' && Number.isFinite(value))
        peak = Math.max(peak, value);
  }
  if (
    previous &&
    previous.min === 0 &&
    Number.isFinite(previous.max) &&
    previous.max >= Math.max(1, peak) &&
    peak / previous.max >= 0.5
  )
    return previous;
  const step = Math.max(1, 10 ** (Math.floor(Math.log10(peak || 1)) - 1));
  const padded = peak * 1.1;
  const rounded = Math.ceil(padded / step) * step;
  return {
    min: 0,
    max: Math.max(1, Number.isFinite(rounded) ? rounded : Number.MAX_VALUE),
  };
}
