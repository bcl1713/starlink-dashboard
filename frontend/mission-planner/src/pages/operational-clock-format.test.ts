import { describe, expect, it } from 'vitest';
import { formatOperationalClockTime } from './operational-clock-format';
describe('formatOperationalClockTime', () => {
  it('renders UTC midnight with an explicit 24-hour clock', () => {
    expect(
      formatOperationalClockTime(Date.UTC(2026, 0, 2, 0, 5, 6), 'UTC')
    ).toBe('00:05:06');
  });
});
it('uses Zulu for legacy configured local clock zones', () => {
  expect(
    formatOperationalClockTime(
      Date.UTC(2026, 6, 2, 0, 5, 6),
      'America/New_York'
    )
  ).toBe('00:05:06');
});
