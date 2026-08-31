import { describe, expect, it } from 'vitest';

import { ExactRollingMean } from './metric-panel-exact-mean';
import exactMeanSource from './metric-panel-exact-mean.ts?raw';

describe('ExactRollingMean', () => {
  it('reverses add and remove exactly when an extreme expires', () => {
    const mean = new ExactRollingMean();

    mean.add(Number.MAX_VALUE);
    mean.add(1);
    mean.add(1);
    mean.remove(Number.MAX_VALUE);

    expect(mean.count).toBe(2);
    expect(mean.mean()).toBe(1);
  });

  it('retains positive subnormal values after removal', () => {
    const mean = new ExactRollingMean();

    mean.add(Number.MAX_VALUE);
    mean.add(Number.MIN_VALUE);
    mean.add(Number.MIN_VALUE);
    mean.remove(Number.MAX_VALUE);

    expect(mean.mean()).toBe(Number.MIN_VALUE);
  });

  it('averages maximum finite values without overflowing', () => {
    const mean = new ExactRollingMean();

    mean.add(Number.MAX_VALUE);
    mean.add(Number.MAX_VALUE);

    expect(mean.mean()).toBe(Number.MAX_VALUE);
  });

  it('normalizes hostile mixed signs without fabricated infinities or zeros', () => {
    const mean = new ExactRollingMean();

    mean.add(Number.MAX_VALUE);
    mean.add(-Number.MAX_VALUE);
    mean.add(Number.MIN_VALUE);
    mean.add(Number.MIN_VALUE);
    mean.add(Number.MIN_VALUE);

    expect(mean.mean()).toBe(Number.MIN_VALUE);
    expect(Object.is(mean.mean(), -0)).toBe(false);
    expect(Number.isFinite(mean.mean())).toBe(true);
  });

  it('adds 1801 distinct exponents and reads without a hidden fold', () => {
    const mean = new ExactRollingMean();

    for (let index = 0; index < 1801; index += 1) {
      mean.add(2 ** (-1022 + index));
    }

    const result = mean.mean();

    expect(mean.count).toBe(1801);
    expect(result).not.toBeNull();
    expect(Number.isFinite(result)).toBe(true);
    expect(Object.is(result, -0)).toBe(false);
  });

  it('keeps the implementation free of exponent-bin maps and iteration', () => {
    expect(exactMeanSource).not.toMatch(
      /\bMap\b|\.keys\(|\.entries\(|for\s*\(/
    );
    expect(exactMeanSource).not.toContain('sumToLowestExponent');
  });
});
