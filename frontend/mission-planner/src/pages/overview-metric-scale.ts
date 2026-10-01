import type {
  OverviewMetricGraphDescriptor,
  ProjectedMetricTraces,
} from './overview-metric-history';

export interface YRange {
  min: number;
  max: number;
}

/** Zero-based, rounded headroom; hysteresis avoids jitter as peaks enter or leave. */
export function metricScale(
  descriptor: OverviewMetricGraphDescriptor,
  projected: ProjectedMetricTraces | undefined,
  previous?: YRange
): YRange {
  if (descriptor.id === 'obstruction' || descriptor.id === 'packet-loss')
    return { min: 0, max: 100 };
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
