import {
  awareInstantToChartEpochSeconds,
  parseAwareTimestampInstant,
  type AwareTimestampInstant,
} from '../../../services/monitoring-validation';
import type { NumericHistorySample } from '../history';
import type { LatencyPanelData, TimeSeriesRow } from './metric-panel-types';

export interface LatencyProjectionInstrumentation {
  parsed: number;
  visited: number;
  enqueued: number;
  dequeued: number;
  minQueueOperations: number;
  maxQueueOperations: number;
}

type ParsedLatencySample = Readonly<{
  timestamp: string;
  epochSeconds: number | null;
  instant: AwareTimestampInstant;
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
  let count = 0;
  let mean = 0;
  let latestCurrent: number | null = null;
  let latestMin: number | null = null;
  let latestMean: number | null = null;
  let latestMax: number | null = null;

  for (const sample of parsed) {
    if (instrumentation) instrumentation.visited += 1;
    const cutoff = shiftInstantSeconds(sample.instant, 300);
    while (
      head < window.length &&
      compareInstants(window[head].instant, cutoff) < 0
    ) {
      const removed = window[head];
      head += 1;
      if (instrumentation) instrumentation.dequeued += 1;
      if (removed.value !== null) {
        if (count === 1) {
          count = 0;
          mean = 0;
        } else {
          mean += (mean - removed.value) / (count - 1);
          count -= 1;
        }
      }
    }
    minHead = dropExpired(minQueue, minHead, cutoff, instrumentation, 'min');
    maxHead = dropExpired(maxQueue, maxHead, cutoff, instrumentation, 'max');

    window.push(sample);
    if (instrumentation) instrumentation.enqueued += 1;
    if (sample.value !== null) {
      count += 1;
      mean += (sample.value - mean) / count;
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

    const min = count === 0 ? null : (minQueue[minHead]?.value ?? null);
    const max = count === 0 ? null : (maxQueue[maxHead]?.value ?? null);
    const rowMean = count === 0 || !Number.isFinite(mean) ? null : mean;
    if (sample.value !== null) {
      latestMin = min;
      latestMean = rowMean;
      latestMax = max;
    }
    if (sample.epochSeconds !== null) {
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
    const instant = parseAwareTimestampInstant(sample.timestamp);
    if (instant === null) continue;
    parsed.push({
      timestamp: sample.timestamp,
      epochSeconds: awareInstantToChartEpochSeconds(instant),
      instant,
      value: validNonnegative(sample.value) ? positiveZero(sample.value) : null,
    });
  }
  return parsed;
}

function dropExpired(
  queue: readonly ParsedLatencySample[],
  head: number,
  cutoff: AwareTimestampInstant,
  instrumentation: LatencyProjectionInstrumentation | undefined,
  kind: 'min' | 'max'
): number {
  let nextHead = head;
  while (
    nextHead < queue.length &&
    compareInstants(queue[nextHead].instant, cutoff) < 0
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

function compareInstants(
  left: AwareTimestampInstant,
  right: AwareTimestampInstant
): number {
  if (left.seconds !== right.seconds)
    return left.seconds < right.seconds ? -1 : 1;
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, '0');
  const rightFraction = right.fraction.padEnd(width, '0');
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
}

function shiftInstantSeconds(
  instant: AwareTimestampInstant,
  seconds: number
): AwareTimestampInstant {
  return {
    seconds: instant.seconds - BigInt(seconds),
    fraction: instant.fraction,
  };
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
