import { z } from 'zod';
import {
  awareTimestampSchema,
  awareTimestampStringToChartEpochSeconds,
  compareAwareTimestampStringToEpochMilliseconds,
  compareAwareTimestampStrings,
} from './monitoring-timestamp-internal';

export { awareTimestampSchema };

export const finiteNumberSchema = z.number().finite();
export const nonNegativeNumberSchema = finiteNumberSchema.min(0);
export const percentSchema = finiteNumberSchema.min(0).max(100);
export const latitudeSchema = finiteNumberSchema.min(-90).max(90);
export const longitudeSchema = finiteNumberSchema.min(-180).max(180);
export const azimuthSchema = finiteNumberSchema.min(0).max(360);

export function compareAwareTimestampInstants(
  first: string,
  second: string
): number {
  return compareAwareTimestampStrings(first, second);
}

export function compareAwareTimestampToEpochMilliseconds(
  timestamp: string,
  epochMilliseconds: number,
  offsetSeconds?: number
): -1 | 0 | 1 | null {
  return compareAwareTimestampStringToEpochMilliseconds(
    timestamp,
    epochMilliseconds,
    offsetSeconds
  );
}

export function awareTimestampToChartEpochSeconds(
  timestamp: string
): number | null {
  return awareTimestampStringToChartEpochSeconds(timestamp);
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
