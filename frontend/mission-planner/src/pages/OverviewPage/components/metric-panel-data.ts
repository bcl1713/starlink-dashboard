import { awareTimestampToChartEpochSeconds } from '../../../services/monitoring-validation';
import type { MonitoringHistory } from '../../../types/monitoring';
import {
  buildThroughputRenderSeries,
  mergeTimestampedSamples,
  type NumericHistorySample,
} from '../history';
import type {
  LatencyPanelData,
  MetricSummary,
  PacketLossPanelData,
  ThroughputPanelData,
  TimeSeriesRow,
} from './metric-panel-types';
import {
  buildLinearLatencyPanel,
  type LatencyProjectionInstrumentation,
} from './metric-panel-latency';
import { buildRawThroughputRows } from './metric-panel-throughput';

export type { LatencyProjectionInstrumentation };

export function buildLatencyPanelData(
  history: MonitoringHistory,
  now: string
): LatencyPanelData {
  return buildLatencyPanelDataWithInstrumentation(history, now);
}

export function buildLatencyPanelDataWithInstrumentation(
  history: MonitoringHistory,
  now: string,
  instrumentation?: LatencyProjectionInstrumentation
): LatencyPanelData {
  const samples = selectCanonicalSeries(history, 'latency_ms', now);
  if (samples === null) return emptyLatency();
  return buildLinearLatencyPanel(samples, instrumentation);
}

export function buildThroughputPanelData(
  history: MonitoringHistory,
  now: string
): ThroughputPanelData {
  const download = selectCanonicalSeries(history, 'throughput_down_mbps', now);
  const upload = selectCanonicalSeries(history, 'throughput_up_mbps', now);
  if (download === null || upload === null) return emptyThroughput();
  const rendered = buildThroughputRenderSeries(download, upload);
  const chartRows = rowsFromSamples(
    rendered.map((row) => ({
      timestamp: row.timestamp,
      value: [row.downloadMbps, row.uploadMbps] as const,
    })),
    (sample) => {
      const [down, up] = sample.value;
      return [
        validNonnegative(down) ? down : null,
        typeof up === 'number' && Number.isFinite(up) ? up : null,
      ];
    }
  );
  const tableRows = rowsFromSamples(
    buildRawThroughputRows(download, upload),
    (sample) => sample.value
  );
  return freezePanel({
    chartRows: collapseChartRows(chartRows),
    tableRows,
    download: summarize(download, validNonnegative),
    upload: summarize(upload, validNonnegative),
  });
}

export function buildPacketLossPanelData(
  history: MonitoringHistory,
  now: string
): PacketLossPanelData {
  const samples = selectCanonicalSeries(history, 'packet_loss_percent', now);
  if (samples === null) return emptyPacketLoss();
  const tableRows = rowsFromSamples(samples, (sample) => [
    validPercent(sample.value) ? sample.value : null,
  ]);
  const summary = summarize(samples, validPercent);
  return freezePanel({
    chartRows: collapseChartRows(tableRows),
    tableRows,
    summary: freezeObject({
      current: summary.current,
      mean: summary.mean,
      max: summary.max,
    }),
  });
}

function selectCanonicalSeries(
  history: MonitoringHistory,
  metric: MonitoringHistory['series'][number]['metric'],
  now: string
): readonly NumericHistorySample[] | null {
  const matches = history.series.filter((series) => series.metric === metric);
  if (matches.length !== 1) return null;
  try {
    return mergeTimestampedSamples([], matches[0].samples, now);
  } catch {
    return null;
  }
}

function rowsFromSamples<T extends { timestamp: string; value: unknown }>(
  samples: readonly T[],
  values: (
    sample: T,
    index: number,
    all: readonly T[]
  ) => readonly (number | null)[]
): readonly TimeSeriesRow[] {
  return samples
    .map((sample, index, all) => {
      const epochSeconds = awareTimestampToChartEpochSeconds(sample.timestamp);
      if (epochSeconds === null) return null;
      return freezeObject({
        timestamp: sample.timestamp,
        epochSeconds,
        values: freezeArray(values(sample, index, all).map(positiveZeroOrNull)),
      });
    })
    .filter((row): row is TimeSeriesRow => row !== null);
}

function collapseChartRows(
  rows: readonly TimeSeriesRow[]
): readonly TimeSeriesRow[] {
  const byEpoch = new Map<number, TimeSeriesRow>();
  for (const row of rows) byEpoch.set(row.epochSeconds, row);
  return freezeArray([...byEpoch.values()]);
}

function summarize(
  samples: readonly NumericHistorySample[],
  accepts: (value: unknown) => value is number
): MetricSummary {
  const values = samples
    .filter((sample) => accepts(sample.value))
    .map((sample) => sample.value as number);
  const current = values.length === 0 ? null : values[values.length - 1];
  const [min, mean, max] = summarizeValues(values);
  return freezeSummary(current, min, mean, max);
}

function summarizeValues(
  values: readonly number[]
): readonly [number | null, number | null, number | null] {
  if (values.length === 0) return [null, null, null];
  const min = Math.min(...values);
  const max = Math.max(...values);
  let count = 0;
  let mean = 0;
  for (const value of values) {
    count += 1;
    mean += (value - mean) / count;
  }
  return [positiveZero(min), positiveZero(mean), positiveZero(max)];
}

function validNonnegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function validPercent(value: unknown): value is number {
  return validNonnegative(value) && value <= 100;
}

function freezeSummary(
  current: number | null,
  min: number | null,
  mean: number | null,
  max: number | null
): MetricSummary {
  return freezeObject({
    current: positiveZeroOrNull(current),
    min: positiveZeroOrNull(min),
    mean: positiveZeroOrNull(mean),
    max: positiveZeroOrNull(max),
  });
}

function emptySummary(): MetricSummary {
  return freezeSummary(null, null, null, null);
}

function emptyLatency(): LatencyPanelData {
  return freezePanel({ chartRows: [], tableRows: [], summary: emptySummary() });
}

function emptyThroughput(): ThroughputPanelData {
  return freezePanel({
    chartRows: [],
    tableRows: [],
    download: emptySummary(),
    upload: emptySummary(),
  });
}

function emptyPacketLoss(): PacketLossPanelData {
  return freezePanel({
    chartRows: [],
    tableRows: [],
    summary: freezeObject({ current: null, mean: null, max: null }),
  });
}

function freezePanel<T extends object>(panel: T): T {
  for (const [key, value] of Object.entries(panel)) {
    if (Array.isArray(value)) {
      (panel as Record<string, unknown>)[key] = freezeArray(value);
    }
  }
  return freezeObject(panel);
}

function freezeArray<T>(value: readonly T[]): readonly T[] {
  return Object.freeze([...value]);
}

function freezeObject<T extends object>(value: T): T {
  return Object.freeze(value);
}

function positiveZeroOrNull(value: number | null): number | null {
  return value === null ? null : positiveZero(value);
}

function positiveZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}
