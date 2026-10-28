import { expect, it } from 'vitest';
import { eventUtc, timelineTime } from './eventFormatting';

it('formats fixed 24-hour Zulu and normalizes dates before deciding rollover', () => {
  expect(eventUtc('2026-10-17T23:05:44.123456Z')).toBe(
    '2026-10-17 23:05:44 Zulu'
  );
  expect(
    timelineTime('2026-10-18T01:05:00+02:00', '2026-10-17T22:00:00Z')
  ).toBe('23:05 Zulu');
  expect(timelineTime('2026-10-18T00:05:00Z', '2026-10-17T23:59:00Z')).toBe(
    '2026-10-18 00:05 Zulu'
  );
  expect(eventUtc('invalid')).toBe('Time Unknown');
});
