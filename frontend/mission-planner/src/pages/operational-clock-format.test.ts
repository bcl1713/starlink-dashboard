import { describe, expect, it } from 'vitest';
import { formatOperationalClockTime } from './operational-clock-format';
describe('formatOperationalClockTime', () => {
  it('renders UTC midnight with an explicit 24-hour clock', () => {
    expect(
      formatOperationalClockTime(Date.UTC(2026, 0, 2, 0, 5, 6), 'UTC')
    ).toBe('00:05:06');
  });
  it.each([
    ['2026-01-02T00:05:06Z', 'America/New_York', '19:05:06'],
    ['2026-07-02T00:05:06Z', 'America/New_York', '20:05:06'],
    ['2026-01-02T00:05:06Z', 'America/Chicago', '18:05:06'],
    ['2026-07-02T00:05:06Z', 'America/Chicago', '19:05:06'],
    ['2026-07-02T00:05:06Z', 'Asia/Tokyo', '09:05:06'],
    ['2026-03-08T06:59:59Z', 'America/New_York', '01:59:59'],
    ['2026-03-08T07:00:00Z', 'America/New_York', '03:00:00'],
  ])('renders %s in configured zone %s as %s', (timestamp, zone, expected) => {
    expect(formatOperationalClockTime(Date.parse(timestamp), zone)).toBe(
      expected
    );
  });
});
