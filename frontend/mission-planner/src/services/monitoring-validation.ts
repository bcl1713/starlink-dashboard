import { z } from 'zod';

export const awareTimestampSchema = z.iso.datetime({ offset: true });
export const finiteNumberSchema = z.number().finite();
export const nonNegativeNumberSchema = finiteNumberSchema.min(0);
export const percentSchema = finiteNumberSchema.min(0).max(100);
export const latitudeSchema = finiteNumberSchema.min(-90).max(90);
export const longitudeSchema = finiteNumberSchema.min(-180).max(180);
export const azimuthSchema = finiteNumberSchema.min(0).max(360);

export interface AwareTimestampInstant {
  readonly seconds: bigint;
  readonly fraction: string;
}

const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.([0-9]+))?)?(Z|[+-]\d{2}:\d{2})$/;
const unixEpochDay = daysFromCivil('1970', '01', '01');
const timeClipSeconds = 8_640_000_000_000n;

export function compareAwareTimestampInstants(
  first: string,
  second: string
): number {
  const left = parseInstant(first);
  const right = parseInstant(second);
  if (left === null || right === null) return 0;
  if (left.seconds !== right.seconds) {
    return left.seconds < right.seconds ? -1 : 1;
  }
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, '0');
  const rightFraction = right.fraction.padEnd(width, '0');
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
}

export function parseAwareTimestampInstant(
  timestamp: string
): AwareTimestampInstant | null {
  return parseInstant(timestamp);
}

export function compareAwareTimestampToEpochMilliseconds(
  timestamp: string,
  epochMilliseconds: number,
  offsetSeconds?: number
): -1 | 0 | 1 | null {
  const instant = parseInstant(timestamp);
  if (
    instant === null ||
    !Number.isSafeInteger(epochMilliseconds) ||
    (offsetSeconds !== undefined && !Number.isSafeInteger(offsetSeconds))
  ) {
    return null;
  }
  const targetMilliseconds =
    BigInt(epochMilliseconds) + BigInt(offsetSeconds ?? 0) * 1000n;
  const width = Math.max(instant.fraction.length, 3);
  const scale = 10n ** BigInt(width);
  const unixSeconds = instant.seconds - unixEpochDay * 86_400n;
  const timestampUnits =
    unixSeconds * scale + BigInt(instant.fraction.padEnd(width, '0') || '0');
  const targetUnits = targetMilliseconds * 10n ** BigInt(width - 3);
  if (timestampUnits === targetUnits) return 0;
  return timestampUnits < targetUnits ? -1 : 1;
}

export function awareTimestampToChartEpochSeconds(
  timestamp: string
): number | null {
  const instant = parseInstant(timestamp);
  if (instant === null) return null;
  return awareInstantToChartEpochSeconds(instant);
}

export function awareInstantToChartEpochSeconds(
  instant: AwareTimestampInstant
): number | null {
  const unixSeconds = instant.seconds - unixEpochDay * 86_400n;
  const fraction = instant.fraction.replace(/0+$/, '');
  const scale = 10n ** BigInt(fraction.length);
  const units = unixSeconds * scale + BigInt(fraction || '0');
  const clipUnits = timeClipSeconds * scale;
  if (units < -clipUnits || units > clipUnits) return null;
  const projected =
    Number(unixSeconds) + (fraction === '' ? 0 : Number(`0.${fraction}`));
  return Number.isFinite(projected) ? projected : null;
}

export function isStrictlyChronological(
  timestamps: readonly string[]
): boolean {
  for (let index = 1; index < timestamps.length; index += 1) {
    if (
      compareAwareTimestampInstants(timestamps[index - 1], timestamps[index]) >=
      0
    ) {
      return false;
    }
  }
  return true;
}

function parseInstant(value: string): AwareTimestampInstant | null {
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
    fraction,
  };
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
