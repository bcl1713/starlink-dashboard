import { describe, expect, it } from 'vitest';

import { ExactRollingMean } from './metric-panel-exact-mean';

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
});
