import { z } from 'zod';

export const awareTimestampSchema = z.iso.datetime({ offset: true });

const instantBrand: unique symbol = Symbol('AwareTimestampInstant');

export interface ParsedAwareTimestampInstant {
  readonly [instantBrand]: true;
  readonly seconds: bigint;
  readonly fraction: string;
}

export type ParsedChartTimestamp = Readonly<{
  instant: ParsedAwareTimestampInstant;
  epochSeconds: number;
}>;

const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.([0-9]+))?)?(Z|[+-]\d{2}:\d{2})$/;
const unixEpochDay = daysFromCivil('1970', '01', '01');
const secondsPerDay = 86_400n;
const timeClipSeconds = 8_640_000_000_000n;

export function parseAwareTimestampForChart(
  timestamp: string
): ParsedChartTimestamp | null {
  if (typeof timestamp !== 'string') return null;
  const instant = parseAwareTimestampInstant(timestamp);
  if (instant === null) return null;
  const epochSeconds = awareInstantToChartEpochSeconds(instant);
  return epochSeconds === null ? null : { instant, epochSeconds };
}

export function compareAwareTimestampStrings(
  first: string,
  second: string
): number {
  const left = parseAwareTimestampInstant(first);
  const right = parseAwareTimestampInstant(second);
  if (left === null || right === null) return 0;
  return compareAwareTimestampInstants(left, right);
}

export function compareParsedAwareTimestampInstants(
  left: ParsedAwareTimestampInstant,
  right: ParsedAwareTimestampInstant
): number {
  return compareAwareTimestampInstants(left, right);
}

export function compareAwareTimestampStringToEpochMilliseconds(
  timestamp: string,
  epochMilliseconds: number,
  offsetSeconds?: number
): -1 | 0 | 1 | null {
  const instant = parseAwareTimestampInstant(timestamp);
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
  const unixSeconds = instant.seconds - unixEpochDay * secondsPerDay;
  const timestampUnits =
    unixSeconds * scale + BigInt(instant.fraction.padEnd(width, '0') || '0');
  const targetUnits = targetMilliseconds * 10n ** BigInt(width - 3);
  if (timestampUnits === targetUnits) return 0;
  return timestampUnits < targetUnits ? -1 : 1;
}

export function awareTimestampStringToChartEpochSeconds(
  timestamp: string
): number | null {
  return parseAwareTimestampForChart(timestamp)?.epochSeconds ?? null;
}

export function shiftParsedAwareTimestampSeconds(
  instant: ParsedAwareTimestampInstant,
  seconds: number
): ParsedAwareTimestampInstant {
  return brandInstant({
    seconds: instant.seconds - BigInt(seconds),
    fraction: instant.fraction,
  });
}

export function formatAwareTimestampUtc(timestamp: string): string | null {
  if (typeof timestamp !== 'string') return null;
  const instant = parseAwareTimestampInstant(timestamp);
  if (instant === null) return null;
  const day = floorDiv(instant.seconds, secondsPerDay);
  const secondOfDay = floorMod(instant.seconds, secondsPerDay);
  const civil = civilFromDays(day);
  const hour = secondOfDay / 3_600n;
  const minute = (secondOfDay % 3_600n) / 60n;
  const second = secondOfDay % 60n;
  return `${formatYear(civil.year)}-${pad(civil.month, 2)}-${pad(
    civil.day,
    2
  )} ${pad(hour, 2)}:${pad(minute, 2)}:${pad(second, 2)} UTC`;
}

function parseAwareTimestampInstant(
  value: string
): ParsedAwareTimestampInstant | null {
  const match = timestampPattern.exec(value);
  if (!match || !awareTimestampSchema.safeParse(value).success) return null;
  const [, year, month, day, hour, minute, second, fraction = '', offset] =
    match;
  const localSeconds =
    daysFromCivil(year, month, day) * secondsPerDay +
    BigInt(hour) * 3_600n +
    BigInt(minute) * 60n +
    BigInt(second ?? '0');
  const offsetSeconds = BigInt(offset === 'Z' ? 0 : parseOffsetSeconds(offset));
  return brandInstant({
    seconds: localSeconds - offsetSeconds,
    fraction: fraction.replace(/0+$/, ''),
  });
}

function awareInstantToChartEpochSeconds(
  instant: ParsedAwareTimestampInstant
): number | null {
  const unixSeconds = instant.seconds - unixEpochDay * secondsPerDay;
  if (
    unixSeconds < -timeClipSeconds ||
    unixSeconds > timeClipSeconds ||
    (unixSeconds === timeClipSeconds && instant.fraction !== '')
  ) {
    return null;
  }
  const projected =
    Number(unixSeconds) +
    (instant.fraction === '' ? 0 : fractionToNumber(instant.fraction));
  return Number.isFinite(projected) ? projected : null;
}

function compareAwareTimestampInstants(
  left: ParsedAwareTimestampInstant,
  right: ParsedAwareTimestampInstant
): number {
  if (left.seconds !== right.seconds)
    return left.seconds < right.seconds ? -1 : 1;
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, '0');
  const rightFraction = right.fraction.padEnd(width, '0');
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
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

function civilFromDays(days: bigint): {
  readonly year: bigint;
  readonly month: bigint;
  readonly day: bigint;
} {
  const era = floorDiv(days, 146_097n);
  const dayOfEra = days - era * 146_097n;
  const yearOfEra =
    (dayOfEra - dayOfEra / 1460n + dayOfEra / 36_524n - dayOfEra / 146_096n) /
    365n;
  const year = yearOfEra + era * 400n;
  const dayOfYear =
    dayOfEra - (365n * yearOfEra + yearOfEra / 4n - yearOfEra / 100n);
  const monthPrime = (5n * dayOfYear + 2n) / 153n;
  const day = dayOfYear - (153n * monthPrime + 2n) / 5n + 1n;
  const month = monthPrime + (monthPrime < 10n ? 3n : -9n);
  return {
    year: year + (month <= 2n ? 1n : 0n),
    month,
    day,
  };
}

function floorDiv(dividend: bigint, divisor: bigint): bigint {
  const quotient = dividend / divisor;
  const remainder = dividend % divisor;
  return remainder < 0n ? quotient - 1n : quotient;
}

function floorMod(dividend: bigint, divisor: bigint): bigint {
  const remainder = dividend % divisor;
  return remainder < 0n ? remainder + divisor : remainder;
}

function parseOffsetSeconds(offset: string): number {
  const sign = offset[0] === '-' ? -1 : 1;
  const hours = Number(offset.slice(1, 3));
  const minutes = Number(offset.slice(4, 6));
  return sign * (hours * 3600 + minutes * 60);
}

function fractionToNumber(fraction: string): number {
  return Number(`0.${fraction.slice(0, 20)}`);
}

function pad(value: bigint, width: number): string {
  return value.toString().padStart(width, '0');
}

function formatYear(year: bigint): string {
  if (year < 0n) return `-${(-year).toString().padStart(4, '0')}`;
  return pad(year, 4);
}

function brandInstant(
  value: Omit<ParsedAwareTimestampInstant, typeof instantBrand>
): ParsedAwareTimestampInstant {
  return Object.freeze({ ...value, [instantBrand]: true as const });
}
