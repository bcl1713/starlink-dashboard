import type { NumericHistorySample } from '../history';
import {
  compareParsedAwareTimestampInstants,
  parseAwareTimestampForChart,
  shiftParsedAwareTimestampSeconds,
  type ParsedAwareTimestampInstant,
} from '../../../services/monitoring-timestamp-internal';
import { ExactRollingMean } from './metric-panel-exact-mean';
import type { LatencyPanelData, TimeSeriesRow } from './metric-panel-types';

export interface LatencyProjectionInstrumentation {
  parsed: number;
  visited: number;
  enqueued: number;
  dequeued: number;
  minQueueOperations: number;
  maxQueueOperations: number;
  meanAdds: number;
  meanRemoves: number;
  meanReads: number;
}

type ParsedLatencySample = Readonly<{
  timestamp: string;
  epochSeconds: number;
  instant: ParsedAwareTimestampInstant;
  value: number | null;
}>;

export function buildLinearLatencyPanel(
  samples: readonly NumericHistorySample[],
  instrumentation?: LatencyProjectionInstrumentation
): LatencyPanelData {
  const parsed = parseLatencySamples(samples, instrumentation);
  const tableRows: TimeSeriesRow[] = [];
  const window: ParsedLatencySample[] = [];
  const minQueue: ParsedLatencySample[] = [];
  const maxQueue: ParsedLatencySample[] = [];
  let head = 0;
  let minHead = 0;
  let maxHead = 0;
  const mean = new ExactRollingMean();
  let latestCurrent: number | null = null;
  let latestMin: number | null = null;
  let latestMean: number | null = null;
  let latestMax: number | null = null;

  for (const sample of parsed) {
    if (instrumentation) instrumentation.visited += 1;
    const cutoff = shiftParsedAwareTimestampSeconds(sample.instant, 300);
    while (
      head < window.length &&
      compareParsedAwareTimestampInstants(window[head].instant, cutoff) < 0
    ) {
      const removed = window[head];
      head += 1;
      if (instrumentation) instrumentation.dequeued += 1;
      if (removed.value !== null) {
        mean.remove(removed.value);
        if (instrumentation) instrumentation.meanRemoves += 1;
      }
    }
    minHead = dropExpired(minQueue, minHead, cutoff, instrumentation, 'min');
    maxHead = dropExpired(maxQueue, maxHead, cutoff, instrumentation, 'max');

    window.push(sample);
    if (instrumentation) instrumentation.enqueued += 1;
    if (sample.value !== null) {
      mean.add(sample.value);
      if (instrumentation) instrumentation.meanAdds += 1;
      minHead = pushMonotonic(
        minQueue,
        minHead,
        sample,
        'min',
        instrumentation
      );
      maxHead = pushMonotonic(
        maxQueue,
        maxHead,
        sample,
        'max',
        instrumentation
      );
      latestCurrent = sample.value;
    }

    const min = mean.count === 0 ? null : (minQueue[minHead]?.value ?? null);
    const max = mean.count === 0 ? null : (maxQueue[maxHead]?.value ?? null);
    if (instrumentation) instrumentation.meanReads += 1;
    const rowMean = mean.mean();
    if (sample.value !== null) {
      latestMin = min;
      latestMean = rowMean;
      latestMax = max;
    }
    tableRows.push(
      freezeObject({
        timestamp: sample.timestamp,
        epochSeconds: sample.epochSeconds,
        values: freezeArray(
          [sample.value, min, rowMean, max].map(positiveZeroOrNull)
        ),
      })
    );
  }

  return freezeObject({
    chartRows: collapseChartRows(tableRows),
    tableRows: freezeArray(tableRows),
    summary: freezeObject({
      current: positiveZeroOrNull(latestCurrent),
      min: positiveZeroOrNull(latestMin),
      mean: positiveZeroOrNull(latestMean),
      max: positiveZeroOrNull(latestMax),
    }),
  });
}

function parseLatencySamples(
  samples: readonly NumericHistorySample[],
  instrumentation?: LatencyProjectionInstrumentation
): readonly ParsedLatencySample[] {
  const parsed: ParsedLatencySample[] = [];
  for (const sample of samples) {
    if (instrumentation) instrumentation.parsed += 1;
    const timestamp = parseAwareTimestampForChart(sample.timestamp);
    if (timestamp === null) continue;
    parsed.push({
      timestamp: sample.timestamp,
      epochSeconds: timestamp.epochSeconds,
      instant: timestamp.instant,
      value: validNonnegative(sample.value) ? positiveZero(sample.value) : null,
    });
  }
  return parsed;
}

function dropExpired(
  queue: readonly ParsedLatencySample[],
  head: number,
  cutoff: ParsedAwareTimestampInstant,
  instrumentation: LatencyProjectionInstrumentation | undefined,
  kind: 'min' | 'max'
): number {
  let nextHead = head;
  while (
    nextHead < queue.length &&
    compareParsedAwareTimestampInstants(queue[nextHead].instant, cutoff) < 0
  ) {
    nextHead += 1;
    incrementQueueOperation(instrumentation, kind);
  }
  return nextHead;
}

function pushMonotonic(
  queue: ParsedLatencySample[],
  head: number,
  sample: ParsedLatencySample,
  kind: 'min' | 'max',
  instrumentation: LatencyProjectionInstrumentation | undefined
): number {
  while (
    queue.length > head &&
    shouldPop(queue[queue.length - 1], sample, kind)
  ) {
    queue.pop();
    incrementQueueOperation(instrumentation, kind);
  }
  queue.push(sample);
  incrementQueueOperation(instrumentation, kind);
  return head;
}

function shouldPop(
  queued: ParsedLatencySample,
  sample: ParsedLatencySample,
  kind: 'min' | 'max'
): boolean {
  if (queued.value === null || sample.value === null) return false;
  return kind === 'min'
    ? queued.value >= sample.value
    : queued.value <= sample.value;
}

function incrementQueueOperation(
  instrumentation: LatencyProjectionInstrumentation | undefined,
  kind: 'min' | 'max'
): void {
  if (!instrumentation) return;
  if (kind === 'min') instrumentation.minQueueOperations += 1;
  else instrumentation.maxQueueOperations += 1;
}

function collapseChartRows(
  rows: readonly TimeSeriesRow[]
): readonly TimeSeriesRow[] {
  const byEpoch = new Map<number, TimeSeriesRow>();
  for (const row of rows) byEpoch.set(row.epochSeconds, row);
  return freezeArray([...byEpoch.values()]);
}

function validNonnegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
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
