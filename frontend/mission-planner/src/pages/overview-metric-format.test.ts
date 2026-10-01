import { describe, expect, it } from 'vitest';
import { formatMetricValue, formatMetricAxis } from './overview-metric-format';

describe('Overview metric presentation', () => {
  it.each([
    [7.49, 'ms', '7 ms'],
    [7.5, 'ms', '8 ms'],
    [53.347, 'Mbps', '53.3 Mbps'],
    [53, 'Mbps', '53 Mbps'],
    [0.236, '%', '0.24%'],
    [3, '%', '3%'],
    [0, '%', '0%'],
    [-0, '%', '0%'],
    [0.004, '%', '<0.01%'],
    [0.04, 'Mbps', '<0.1 Mbps'],
    [0.4, 'ms', '<1 ms'],
    [-0.004, '%', '>-0.01%'],
    [-3.236, '%', '-3.24%'],
    [NaN, 'ms', 'Unavailable'],
    [Infinity, 'Mbps', 'Unavailable'],
  ])('formats %s %s as %s', (value, unit, expected) => {
    expect(formatMetricValue(value, unit)).toBe(expected);
  });

  it('bounds extreme finite labels without changing the underlying value', () => {
    const value = Number.MAX_VALUE;
    expect(formatMetricValue(value, 'Mbps')).toBe('1.8e+308 Mbps');
    expect(value).toBe(Number.MAX_VALUE);
  });

  it('keeps exact scale context instead of rounding a bound to zero', () => {
    expect(formatMetricAxis(0.005)).toBe('0.005');
    expect(formatMetricAxis(0.55)).toBe('0.55');
    expect(formatMetricAxis(100)).toBe('100');
    expect(formatMetricAxis(1.1000000000000001)).toBe('1.1');
  });
});
