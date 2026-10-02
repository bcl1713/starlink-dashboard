import type uPlot from 'uplot';
import type {
  OverviewMetricGraphDescriptor,
  ProjectedMetricTraces,
} from './overview-metric-history';
import {
  isLogarithmicMetric,
  PERCENT_LOG_FLOOR,
  type YRange,
} from './overview-metric-scale';

export interface MetricPlotArgs {
  width: number;
  height: number;
  yRange: YRange;
  descriptor: OverviewMetricGraphDescriptor;
}

/** Floor only rendered log values; preserve raw history and missing-sample gaps. */
export function metricPlotData(
  descriptor: OverviewMetricGraphDescriptor,
  projection: ProjectedMetricTraces
): uPlot.AlignedData {
  const traces = [
    projection.max,
    projection.min,
    projection.avg,
    projection.observed,
  ];
  return [
    projection.times,
    ...(isLogarithmicMetric(descriptor)
      ? traces.map((trace) =>
          trace.map((value) =>
            value === null ? null : Math.max(PERCENT_LOG_FLOOR, value)
          )
        )
      : traces),
  ];
}

/** Aligned data must be [times, high, low, average, observed]. */
export function metricPlotOptions({
  width,
  height,
  yRange,
  descriptor,
}: MetricPlotArgs): uPlot.Options {
  const trace = { show: true, spanGaps: false, points: { show: false } };
  return {
    width,
    height,
    padding: [0, 0, 0, 0],
    axes: [{ show: false }, { show: false }],
    legend: { show: false },
    cursor: { show: false },
    scales: {
      x: { time: true, range: (_plot, min, max) => [min, max] },
      // A fixed array would clamp later setScale expansions to the first domain.
      y: {
        ...(isLogarithmicMetric(descriptor)
          ? {
              distr: 3,
              log: 10,
              clamp: () => PERCENT_LOG_FLOOR,
            }
          : {}),
        auto: false,
        range: (_plot, min, max) => [min ?? yRange.min, max ?? yRange.max],
      },
    },
    bands: [{ series: [1, 2], fill: 'rgba(180, 195, 215, 0.14)' }],
    series: [
      {},
      { ...trace, label: 'High', stroke: 'transparent', width: 0 },
      { ...trace, label: 'Low', stroke: 'transparent', width: 0 },
      {
        ...trace,
        label: 'Average',
        stroke: '#e2e8f0',
        width: 1.25,
        dash: [5, 4],
      },
      { ...trace, label: 'Observed', stroke: '#67e8f9', width: 2.25 },
    ],
  };
}
