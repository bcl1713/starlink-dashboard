import { awareTimestampSchema } from '../../services/monitoring-validation';
import type { MonitoringHistory } from '../../types/monitoring';

export type PositionHistoryPoint = Readonly<{
  timestamp: string;
  latitude: number;
  longitude: number;
  altitudeMeters: null;
}>;

export const HISTORY_WINDOW_SECONDS = 1800,
  HISTORY_MAX_SAMPLES = 1801;

export type TimestampedSample<T> = Readonly<{ timestamp: string; value: T }>;

export type NumericHistorySample = TimestampedSample<number | null>;

export interface MetricSummary {
  readonly available: boolean;
  readonly current: number | null;
  readonly min: number | null;
  readonly mean: number | null;
  readonly max: number | null;
  readonly count: number;
}

type ParsedInstant = Readonly<{ seconds: bigint; fraction: string }>;
type PositionSample = TimestampedSample<number> &
  Readonly<{ instant: ParsedInstant }>;
type Stored<T> = Readonly<{
  sample: TimestampedSample<T>;
  instant: ParsedInstant;
}>;
type ThroughputRow = {
  instant: ParsedInstant;
  timestamp?: string;
  download?: number | null;
  upload?: number | null;
};

const UNAVAILABLE_SUMMARY: MetricSummary = {
  available: false,
  current: null,
  min: null,
  mean: null,
  max: null,
  count: 0,
};
const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.([0-9]+))?)?(Z|[+-]\d{2}:\d{2})$/;

export function alignPositionHistory(
  history: MonitoringHistory
): readonly PositionHistoryPoint[] {
  const latitudes = new Map<string, PositionSample>();
  const longitudes = new Map<string, PositionSample>();
  for (const series of history.series) {
    if (
      series.metric !== 'latitude_degrees' &&
      series.metric !== 'longitude_degrees'
    ) {
      continue;
    }
    const target =
      series.metric === 'latitude_degrees' ? latitudes : longitudes;
    for (const sample of series.samples) {
      const instant = parseInstant(sample.timestamp);
      const value = sample.value;
      if (
        instant === null ||
        !isFiniteNumber(value) ||
        (series.metric === 'latitude_degrees'
          ? value < -90 || value > 90
          : value < -180 || value > 180)
      ) {
        continue;
      }
      target.set(instantKey(instant), {
        timestamp: sample.timestamp,
        value: positiveZero(value),
        instant,
      });
    }
  }
  const points: { point: PositionHistoryPoint; instant: ParsedInstant }[] = [];
  for (const [key, latitude] of latitudes) {
    const longitude = longitudes.get(key);
    if (longitude) {
      points.push({
        instant: latitude.instant,
        point: {
          timestamp: latitude.timestamp,
          latitude: latitude.value,
          longitude: longitude.value,
          altitudeMeters: null,
        },
      });
    }
  }
  return points
    .sort((left, right) => compareInstants(left.instant, right.instant))
    .map(({ point }) => point);
}

export function mergeTimestampedSamples<T>(
  lastGood: readonly TimestampedSample<T>[],
  incoming: readonly TimestampedSample<T>[],
  now: string
): readonly TimestampedSample<T>[] {
  const upper = validateNow(now);
  const lower = shiftSeconds(upper, HISTORY_WINDOW_SECONDS);
  const byInstant = new Map<string, Stored<T>>();
  for (const sample of [...lastGood, ...incoming]) {
    const instant = parseInstant(sample.timestamp);
    if (
      instant === null ||
      compareInstants(instant, lower) < 0 ||
      compareInstants(instant, upper) > 0
    ) {
      continue;
    }
    byInstant.set(instantKey(instant), { sample, instant });
  }
  return [...byInstant.values()]
    .sort((left, right) => compareInstants(left.instant, right.instant))
    .slice(-HISTORY_MAX_SAMPLES)
    .map(({ sample }) => ({
      timestamp: sample.timestamp,
      value: sample.value,
    }));
}

export function summarizeLatency(
  samples: readonly NumericHistorySample[],
  now: string
): MetricSummary {
  return summarize(samples, now, 300, (value) => value >= 0);
}

export function summarizePacketLoss(
  samples: readonly NumericHistorySample[],
  now: string,
  windowSeconds: number
): MetricSummary {
  if (!Number.isFinite(windowSeconds) || windowSeconds < 0)
    throw new RangeError('Invalid windowSeconds');
  return summarize(
    samples,
    now,
    windowSeconds,
    (value) => value >= 0 && value <= 100
  );
}

export type ThroughputRenderPoint = Readonly<{
  timestamp: string;
  downloadMbps: number | null;
  uploadMbps: number | null;
}>;

export function buildThroughputRenderSeries(
  download: readonly NumericHistorySample[],
  upload: readonly NumericHistorySample[]
): readonly ThroughputRenderPoint[] {
  const rows = new Map<string, ThroughputRow>();
  applyThroughput(rows, download, 'download');
  applyThroughput(rows, upload, 'upload');
  return [...rows.values()]
    .sort((left, right) => compareInstants(left.instant, right.instant))
    .map((row) => ({
      timestamp: row.timestamp ?? '',
      downloadMbps: row.download ?? null,
      uploadMbps: row.upload ?? null,
    }));
}

function summarize(
  samples: readonly NumericHistorySample[],
  now: string,
  windowSeconds: number,
  accepts: (value: number) => boolean
): MetricSummary {
  const upper = validateNow(now);
  const lower = shiftSeconds(upper, windowSeconds);
  const valid: { value: number; instant: ParsedInstant }[] = [];
  for (const sample of samples) {
    const instant = parseInstant(sample.timestamp);
    if (
      instant !== null &&
      isFiniteNumber(sample.value) &&
      accepts(sample.value) &&
      compareInstants(instant, lower) >= 0 &&
      compareInstants(instant, upper) <= 0
    ) {
      valid.push({ value: sample.value, instant });
    }
  }
  if (valid.length === 0) return UNAVAILABLE_SUMMARY;
  valid.sort((left, right) => compareInstants(left.instant, right.instant));
  let count = 0;
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;
  let mean = 0;
  for (const { value } of valid) {
    count += 1;
    if (value < min) min = value;
    if (value > max) max = value;
    mean += (value - mean) / count;
  }
  return {
    available: true,
    current: positiveZero(valid[valid.length - 1].value),
    min: positiveZero(min),
    mean: Number.isFinite(mean) ? mean : null,
    max: positiveZero(max),
    count,
  };
}

function applyThroughput(
  rows: Map<string, ThroughputRow>,
  samples: readonly NumericHistorySample[],
  kind: 'download' | 'upload'
): void {
  for (const sample of samples) {
    const instant = parseInstant(sample.timestamp);
    if (instant === null) continue;
    const key = instantKey(instant);
    const row = rows.get(key) ?? { instant };
    const value =
      isFiniteNumber(sample.value) && sample.value >= 0
        ? positiveZero(sample.value)
        : null;
    if (kind === 'download') {
      row.download = value;
      row.timestamp = sample.timestamp;
    } else {
      row.upload = value === null ? null : positiveZero(-value);
      row.timestamp ??= sample.timestamp;
    }
    rows.set(key, row);
  }
}

function validateNow(now: string): ParsedInstant {
  const instant = parseInstant(now);
  if (instant === null) throw new RangeError('Invalid now timestamp');
  return instant;
}

function shiftSeconds(instant: ParsedInstant, seconds: number): ParsedInstant {
  const decimal = parseNonnegativeNumberDecimal(seconds);
  const width = Math.max(instant.fraction.length, decimal.scale);
  const scale = 10n ** BigInt(width);
  const current =
    instant.seconds * scale +
    BigInt(instant.fraction.padEnd(width, '0') || '0');
  const shifted =
    current - decimal.units * 10n ** BigInt(width - decimal.scale);
  const shiftedSeconds = floorDiv(shifted, scale);
  const fraction = shifted - shiftedSeconds * scale;
  return {
    seconds: shiftedSeconds,
    fraction: String(fraction).padStart(width, '0').replace(/0+$/, ''),
  };
}

function parseNonnegativeNumberDecimal(value: number): {
  units: bigint;
  scale: number;
} {
  const match = /^(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(String(value));
  if (!match) throw new RangeError('Invalid windowSeconds');
  const digits = `${match[1]}${match[2] ?? ''}`.replace(/^0+(?=\d)/, '');
  const decimalPlaces = (match[2]?.length ?? 0) - Number(match[3] ?? 0);
  if (decimalPlaces <= 0) {
    return { units: BigInt(digits) * 10n ** BigInt(-decimalPlaces), scale: 0 };
  }
  return { units: BigInt(digits), scale: decimalPlaces };
}

function parseInstant(value: string): ParsedInstant | null {
  const match = timestampPattern.exec(value);
  if (!match || !awareTimestampSchema.safeParse(value).success) return null;
  const [, year, month, day, hour, minute, second, fraction = '', offset] =
    match;
  const offsetSign = offset[0] === '-' ? -1 : 1;
  const offsetSeconds =
    offset === 'Z' ? 0n : BigInt(offsetSign * parseOffsetSeconds(offset));
  const localSeconds =
    daysFromCivil(year, month, day) * 86_400n +
    BigInt(hour) * 3_600n +
    BigInt(minute) * 60n +
    BigInt(second ?? '0');
  return {
    seconds: localSeconds - offsetSeconds,
    fraction: fraction.replace(/0+$/, ''),
  };
}

function compareInstants(left: ParsedInstant, right: ParsedInstant): number {
  if (left.seconds !== right.seconds)
    return left.seconds < right.seconds ? -1 : 1;
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, '0');
  const rightFraction = right.fraction.padEnd(width, '0');
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
}

function instantKey(instant: ParsedInstant): string {
  return `${instant.seconds}:${instant.fraction}`;
}

function daysFromCivil(year: string, month: string, day: string): bigint {
  let adjustedYear = BigInt(year);
  const monthNumber = BigInt(month);
  if (monthNumber <= 2n) adjustedYear -= 1n;
  const era =
    adjustedYear >= 0n ? adjustedYear / 400n : (adjustedYear - 399n) / 400n;
  const yearOfEra = adjustedYear - era * 400n;
  const monthPrime = monthNumber + (monthNumber > 2n ? -3n : 9n);
  const dayOfYear = (153n * monthPrime + 2n) / 5n + BigInt(day) - 1n;
  const dayOfEra =
    yearOfEra * 365n + yearOfEra / 4n - yearOfEra / 100n + dayOfYear;
  return era * 146_097n + dayOfEra;
}

function floorDiv(dividend: bigint, divisor: bigint): bigint {
  const quotient = dividend / divisor;
  return dividend % divisor < 0n ? quotient - 1n : quotient;
}

function parseOffsetSeconds(offset: string): number {
  return Number(offset.slice(1, 3)) * 3600 + Number(offset.slice(4, 6)) * 60;
}

function positiveZero(value: number): number {
  return Object.is(value, -0) ? 0 : value;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}
