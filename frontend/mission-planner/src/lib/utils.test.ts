import { afterEach, expect, it } from 'vitest';
import { formatTime24Hour, toISO8601 } from './utils';
const originalTimezone = process.env.TZ;
afterEach(() => {
  process.env.TZ = originalTimezone;
});
it('treats an entered unzoned calendar value as Zulu even in a daylight-saving timezone', () => {
  process.env.TZ = 'America/New_York';
  expect(toISO8601('2026-07-01T00:05')).toBe('2026-07-01T00:05:00.000Z');
  expect(toISO8601('2026-07-01T00:05:00Z')).toBe('2026-07-01T00:05:00.000Z');
});
it('renders midnight as 00 hours on the UTC calendar day with an explicit Zulu label', () => {
  process.env.TZ = 'America/Los_Angeles';
  const label = formatTime24Hour('2026-07-01T00:05:06Z');
  expect(label).toContain('00:05:06');
  expect(label).toContain('07/01/2026');
  expect(label).toContain('Zulu');
});
