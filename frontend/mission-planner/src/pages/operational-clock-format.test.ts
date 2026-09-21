import { describe, expect, it } from 'vitest';
import { formatOperationalClockTime } from './operational-clock-format';
describe('formatOperationalClockTime', () => {
  it('renders UTC midnight with an explicit 24-hour clock', () => {
    expect(
      formatOperationalClockTime(Date.UTC(2026, 0, 2, 0, 5, 6), 'UTC')
    ).toBe('00:05:06');
  });
});
