import type {
  OverviewMetricGraphDescriptor,
  ProjectedMetricHistory,
} from './overview-metric-history';

export interface YRange {
  min: number;
  max: number;
}

/** Zero-based, rounded headroom; hold an accepted domain until a peak exceeds it. */
export function metricScale(
  descriptor: OverviewMetricGraphDescriptor,
  projected: ProjectedMetricHistory | undefined,
  previous?: YRange
): YRange {
  if (descriptor.id === 'obstruction') return { min: 0, max: 100 };
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
    previous.max >= Math.max(1, peak)
  )
    return previous;
  const step = Math.max(
    descriptor.id === 'packet-loss' ? 0.1 : 1,
    10 ** (Math.floor(Math.log10(peak || 1)) - 1)
  );
  const padded = peak * 1.1;
  const rounded = Math.ceil(padded / step) * step;
  return {
    min: 0,
    max: Math.max(1, Number.isFinite(rounded) ? rounded : Number.MAX_VALUE),
  };
}
