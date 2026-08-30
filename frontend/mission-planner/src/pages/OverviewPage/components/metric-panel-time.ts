import { awareTimestampToChartEpochSeconds } from '../../../services/monitoring-validation';

type InstantParts = Readonly<{
  seconds: bigint;
  secondOfDay: bigint;
}>;

const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.[0-9]+)?)?(Z|[+-]\d{2}:\d{2})$/;

export function formatUtcTimestamp(timestamp: string): string {
  const instant = parseInstant(timestamp);
  if (instant === null) return 'Unavailable';
  const day = floorDiv(instant.seconds, 86_400n);
  const secondOfDay = instant.secondOfDay;
  const civil = civilFromDays(day);
  const hour = secondOfDay / 3_600n;
  const minute = (secondOfDay % 3_600n) / 60n;
  const second = secondOfDay % 60n;
  return `${pad(civil.year, 4)}-${pad(civil.month, 2)}-${pad(
    civil.day,
    2
  )} ${pad(hour, 2)}:${pad(minute, 2)}:${pad(second, 2)} UTC`;
}

function parseInstant(timestamp: string): InstantParts | null {
  if (awareTimestampToChartEpochSeconds(timestamp) === null) return null;
  const match = timestampPattern.exec(timestamp);
  if (!match) return null;
  const [, year, month, day, hour, minute, second = '00', offset] = match;
  const localSeconds =
    daysFromCivil(year, month, day) * 86_400n +
    BigInt(hour) * 3_600n +
    BigInt(minute) * 60n +
    BigInt(second);
  const utcSeconds =
    localSeconds - BigInt(offset === 'Z' ? 0 : parseOffsetSeconds(offset));
  return {
    seconds: utcSeconds,
    secondOfDay: floorMod(utcSeconds, 86_400n),
  };
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

function parseOffsetSeconds(offset: string): number {
  const sign = offset[0] === '-' ? -1 : 1;
  const hours = Number(offset.slice(1, 3));
  const minutes = Number(offset.slice(4, 6));
  return sign * (hours * 3600 + minutes * 60);
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

function pad(value: bigint, width: number): string {
  return value.toString().padStart(width, '0');
}
