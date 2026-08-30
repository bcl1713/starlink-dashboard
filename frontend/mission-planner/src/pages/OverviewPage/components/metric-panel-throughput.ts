import { compareAwareTimestampInstants } from '../../../services/monitoring-validation';
import type { NumericHistorySample } from '../history';

type ThroughputValues = readonly [number | null, number | null];

export interface RawThroughputRow {
  readonly timestamp: string;
  readonly value: ThroughputValues;
}

export function buildRawThroughputRows(
  download: readonly NumericHistorySample[],
  upload: readonly NumericHistorySample[]
): readonly RawThroughputRow[] {
  const entries = [
    ...download.map((sample) => ({ kind: 'download' as const, sample })),
    ...upload.map((sample) => ({ kind: 'upload' as const, sample })),
  ].sort((left, right) =>
    compareAwareTimestampInstants(left.sample.timestamp, right.sample.timestamp)
  );
  const rows: { timestamp: string; value: [number | null, number | null] }[] =
    [];
  for (const entry of entries) {
    const previous = rows.at(-1);
    const sameInstant =
      previous !== undefined &&
      compareAwareTimestampInstants(
        previous.timestamp,
        entry.sample.timestamp
      ) === 0;
    const row =
      sameInstant && previous
        ? previous
        : {
            timestamp: entry.sample.timestamp,
            value: [null, null] as [number | null, number | null],
          };
    const value = validNonnegative(entry.sample.value)
      ? positiveZero(entry.sample.value)
      : null;
    if (entry.kind === 'download') {
      row.timestamp = entry.sample.timestamp;
      row.value[0] = value;
    } else {
      row.value[1] = value;
    }
    if (!sameInstant) rows.push(row);
  }
  return rows.map((row) => ({
    timestamp: row.timestamp,
    value: Object.freeze([...row.value]) as ThroughputValues,
  }));
}

function validNonnegative(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function positiveZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}
