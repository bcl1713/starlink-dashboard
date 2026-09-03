import { z } from 'zod';

const MAX_EXTERNAL_TEXT = 200;
const MAX_INSTANT_LENGTH = 32;
const instantParts =
  /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/;

export const finite = z.number().finite();
export const instant = z
  .string()
  .max(MAX_INSTANT_LENGTH)
  .pipe(z.string().regex(instantParts).datetime({ offset: true }));
export const text = z.string().max(MAX_EXTERNAL_TEXT);
export const coordinate = z.strictObject({
  latitude: finite.min(-90).max(90),
  longitude: finite.min(-180).max(180),
});

type ExactInstant = {
  epochSecond: bigint;
  fraction: bigint;
  precision: number;
};

function parseExactInstant(value: string): ExactInstant {
  if (value.length > MAX_INSTANT_LENGTH) throw new Error('invalid instant');
  const match = instantParts.exec(value);
  if (!match) throw new Error('invalid instant');
  const wholeSecond = Date.parse(`${match[1]}${match[3]}`);
  if (!Number.isFinite(wholeSecond) || wholeSecond % 1000 !== 0) {
    throw new Error('invalid instant');
  }
  const fractionDigits = (match[2] ?? '').replace(/0+$/, '');
  return {
    epochSecond: BigInt(wholeSecond / 1000),
    fraction: BigInt(fractionDigits || '0'),
    precision: fractionDigits.length,
  };
}

function fractionAtPrecision(instant: ExactInstant, precision: number): bigint {
  return instant.fraction * 10n ** BigInt(precision - instant.precision);
}

export function compareInstants(left: string, right: string): number {
  const leftInstant = parseExactInstant(left);
  const rightInstant = parseExactInstant(right);
  if (leftInstant.epochSecond < rightInstant.epochSecond) return -1;
  if (leftInstant.epochSecond > rightInstant.epochSecond) return 1;
  const precision = Math.max(leftInstant.precision, rightInstant.precision);
  const leftFraction = fractionAtPrecision(leftInstant, precision);
  const rightFraction = fractionAtPrecision(rightInstant, precision);
  return leftFraction < rightFraction
    ? -1
    : leftFraction > rightFraction
      ? 1
      : 0;
}

export function instantsDifferBySeconds(
  start: string,
  end: string,
  seconds: number
): boolean {
  const startInstant = parseExactInstant(start);
  const endInstant = parseExactInstant(end);
  return (
    endInstant.epochSecond - startInstant.epochSecond === BigInt(seconds) &&
    compareFractions(startInstant, endInstant)
  );
}

function compareFractions(left: ExactInstant, right: ExactInstant): boolean {
  const precision = Math.max(left.precision, right.precision);
  return (
    fractionAtPrecision(left, precision) ===
    fractionAtPrecision(right, precision)
  );
}
