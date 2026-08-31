const doubleView = new DataView(new ArrayBuffer(8));
const fractionMask = (1n << 52n) - 1n;
const hiddenBit = 1n << 52n;

type DoubleParts = Readonly<{
  coefficient: bigint;
  exponent: number;
}>;

export class ExactRollingMean {
  readonly #bins = new Map<number, bigint>();
  #count = 0;

  get count(): number {
    return this.#count;
  }

  add(value: number): void {
    this.#addParts(decomposeFiniteDouble(value), 1n);
    this.#count += 1;
  }

  remove(value: number): void {
    this.#addParts(decomposeFiniteDouble(value), -1n);
    this.#count -= 1;
  }

  mean(): number | null {
    if (this.#count === 0) return null;
    const total = this.#sumToLowestExponent();
    if (total.coefficient === 0n) return 0;
    return rationalToNearestDouble(
      total.coefficient,
      total.exponent,
      this.#count
    );
  }

  #addParts(parts: DoubleParts, direction: bigint): void {
    const next =
      (this.#bins.get(parts.exponent) ?? 0n) + parts.coefficient * direction;
    if (next === 0n) this.#bins.delete(parts.exponent);
    else this.#bins.set(parts.exponent, next);
  }

  #sumToLowestExponent(): DoubleParts {
    let lowest: number | null = null;
    for (const exponent of this.#bins.keys()) {
      if (lowest === null || exponent < lowest) lowest = exponent;
    }
    if (lowest === null) return { coefficient: 0n, exponent: 0 };

    let coefficient = 0n;
    for (const [exponent, value] of this.#bins) {
      coefficient += value << BigInt(exponent - lowest);
    }
    return { coefficient, exponent: lowest };
  }
}

function decomposeFiniteDouble(value: number): DoubleParts {
  doubleView.setFloat64(0, value, false);
  const high = BigInt(doubleView.getUint32(0, false));
  const low = BigInt(doubleView.getUint32(4, false));
  const bits = (high << 32n) | low;
  const sign = bits >> 63n;
  const rawExponent = Number((bits >> 52n) & 0x7ffn);
  const fraction = bits & fractionMask;
  const signed = sign === 1n ? -1n : 1n;

  if (rawExponent === 0) {
    return { coefficient: signed * fraction, exponent: -1074 };
  }

  return {
    coefficient: signed * (hiddenBit + fraction),
    exponent: rawExponent - 1075,
  };
}

function rationalToNearestDouble(
  signedNumerator: bigint,
  exponent: number,
  divisor: number
): number | null {
  const sign = signedNumerator < 0n ? -1 : 1;
  const numerator = signedNumerator < 0n ? -signedNumerator : signedNumerator;
  const denominator = BigInt(divisor);
  const binaryExponent = findBinaryExponent(numerator, exponent, denominator);
  const targetExponent = binaryExponent < -1022 ? -1074 : binaryExponent - 52;
  let significand = divideRoundedToEven(
    numerator,
    exponent - targetExponent,
    denominator
  );

  if (significand === 0n) return 0;

  let adjustedTargetExponent = targetExponent;
  if (binaryExponent >= -1022 && significand === 1n << 53n) {
    significand >>= 1n;
    adjustedTargetExponent += 1;
  }

  const mean = Number(significand) * 2 ** adjustedTargetExponent;
  if (!Number.isFinite(mean)) return null;
  return sign < 0 ? -mean : mean;
}

function findBinaryExponent(
  numerator: bigint,
  exponent: number,
  denominator: bigint
): number {
  let candidate =
    bitLength(numerator) - 1 + exponent - (bitLength(denominator) - 1);
  while (
    compareScaledToPower(numerator, exponent, denominator, candidate) < 0
  ) {
    candidate -= 1;
  }
  while (
    compareScaledToPower(numerator, exponent, denominator, candidate + 1) >= 0
  ) {
    candidate += 1;
  }
  return candidate;
}

function compareScaledToPower(
  numerator: bigint,
  exponent: number,
  denominator: bigint,
  power: number
): number {
  const shift = power - exponent;
  const [left, right] =
    shift >= 0
      ? [numerator, denominator << BigInt(shift)]
      : [numerator << BigInt(-shift), denominator];
  if (left < right) return -1;
  if (left > right) return 1;
  return 0;
}

function divideRoundedToEven(
  numerator: bigint,
  shift: number,
  denominator: bigint
): bigint {
  const scaledNumerator = shift >= 0 ? numerator << BigInt(shift) : numerator;
  const scaledDenominator =
    shift >= 0 ? denominator : denominator << BigInt(-shift);
  const quotient = scaledNumerator / scaledDenominator;
  const remainder = scaledNumerator % scaledDenominator;
  const doubledRemainder = remainder * 2n;
  if (doubledRemainder > scaledDenominator) return quotient + 1n;
  if (doubledRemainder < scaledDenominator) return quotient;
  return quotient % 2n === 0n ? quotient : quotient + 1n;
}

function bitLength(value: bigint): number {
  return value.toString(2).length;
}
