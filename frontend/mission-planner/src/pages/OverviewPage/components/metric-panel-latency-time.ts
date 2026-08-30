import { awareTimestampSchema } from '../../../services/monitoring-validation';

export type LatencyTimestampInstant = Readonly<{
  seconds: bigint;
  fraction: string;
}>;

const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.([0-9]+))?)?(Z|[+-]\d{2}:\d{2})$/;
const unixEpochDay = daysFromCivil('1970', '01', '01');
const timeClipSeconds = 8_640_000_000_000n;

export function parseLatencyTimestampInstant(
  timestamp: string
): Readonly<{ instant: LatencyTimestampInstant; epochSeconds: number }> | null {
  const instant = parseInstant(timestamp);
  if (instant === null) return null;
  const epochSeconds = instantToChartEpochSeconds(instant);
  return epochSeconds === null ? null : { instant, epochSeconds };
}

export function compareLatencyInstants(
  left: LatencyTimestampInstant,
  right: LatencyTimestampInstant
): number {
  if (left.seconds !== right.seconds)
    return left.seconds < right.seconds ? -1 : 1;
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, '0');
  const rightFraction = right.fraction.padEnd(width, '0');
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
}

export function shiftLatencyInstantSeconds(
  instant: LatencyTimestampInstant,
  seconds: number
): LatencyTimestampInstant {
  return {
    seconds: instant.seconds - BigInt(seconds),
    fraction: instant.fraction,
  };
}

function parseInstant(value: string): LatencyTimestampInstant | null {
  const match = timestampPattern.exec(value);
  if (!match || !awareTimestampSchema.safeParse(value).success) return null;
  const [, year, month, day, hour, minute, second, fraction = '', offset] =
    match;
  const localSeconds =
    daysFromCivil(year, month, day) * 86_400n +
    BigInt(hour) * 3_600n +
    BigInt(minute) * 60n +
    BigInt(second ?? '0');
  const offsetSeconds = BigInt(offset === 'Z' ? 0 : parseOffsetSeconds(offset));
  return {
    seconds: localSeconds - offsetSeconds,
    fraction: fraction.replace(/0+$/, ''),
  };
}

function instantToChartEpochSeconds(
  instant: LatencyTimestampInstant
): number | null {
  const unixSeconds = instant.seconds - unixEpochDay * 86_400n;
  if (unixSeconds < -timeClipSeconds || unixSeconds > timeClipSeconds) {
    return null;
  }
  const projected =
    Number(unixSeconds) +
    (instant.fraction === ''
      ? 0
      : Number(`0.${instant.fraction.slice(0, 20)}`));
  return Number.isFinite(projected) ? projected : null;
}

function daysFromCivil(year: string, month: string, day: string): bigint {
  let adjustedYear = BigInt(year);
  const monthNumber = BigInt(month);
  if (monthNumber <= 2n) adjustedYear -= 1n;
  const era = floorDiv(adjustedYear, 400n);
  const yearOfEra = adjustedYear - era * 400n;
  const monthPrime = monthNumber + (monthNumber > 2n ? -3n : 9n);
  const dayOfYear = (153n * monthPrime + 2n) / 5n + BigInt(day) - 1n;
  const dayOfEra =
    yearOfEra * 365n + yearOfEra / 4n - yearOfEra / 100n + dayOfYear;
  return era * 146_097n + dayOfEra;
}

function floorDiv(dividend: bigint, divisor: bigint): bigint {
  const quotient = dividend / divisor;
  const remainder = dividend % divisor;
  return remainder < 0n ? quotient - 1n : quotient;
}

function parseOffsetSeconds(offset: string): number {
  const sign = offset[0] === '-' ? -1 : 1;
  const hours = Number(offset.slice(1, 3));
  const minutes = Number(offset.slice(4, 6));
  return sign * (hours * 3600 + minutes * 60);
}
