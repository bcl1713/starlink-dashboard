import { z } from 'zod';

export const awareTimestampSchema = z.iso.datetime({ offset: true });
export const finiteNumberSchema = z.number().finite();
export const nonNegativeNumberSchema = finiteNumberSchema.min(0);
export const percentSchema = finiteNumberSchema.min(0).max(100);
export const latitudeSchema = finiteNumberSchema.min(-90).max(90);
export const longitudeSchema = finiteNumberSchema.min(-180).max(180);
export const azimuthSchema = finiteNumberSchema.min(0).max(360);

interface ParsedInstant {
  seconds: bigint;
  fraction: string;
}

const timestampPattern =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.([0-9]+))?(Z|[+-]\d{2}:\d{2})$/;

export function compareAwareTimestampInstants(
  first: string,
  second: string
): number {
  const left = parseInstant(first);
  const right = parseInstant(second);
  if (left.seconds !== right.seconds) {
    return left.seconds < right.seconds ? -1 : 1;
  }
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, '0');
  const rightFraction = right.fraction.padEnd(width, '0');
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
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

function parseInstant(value: string): ParsedInstant {
  const match = timestampPattern.exec(value);
  if (!match) throw new Error('invalid aware timestamp');
  const [, year, month, day, hour, minute, second, fraction = '', offset] =
    match;
  const utcMilliseconds = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second)
  );
  const offsetSeconds = offset === 'Z' ? 0 : parseOffsetSeconds(offset);
  return {
    seconds: BigInt(Math.trunc(utcMilliseconds / 1000) - offsetSeconds),
    fraction,
  };
}

function parseOffsetSeconds(offset: string): number {
  const sign = offset[0] === '-' ? -1 : 1;
  const hours = Number(offset.slice(1, 3));
  const minutes = Number(offset.slice(4, 6));
  return sign * (hours * 3600 + minutes * 60);
}
