import { describe, expect, it } from 'vitest';
import { millisecondsUntilNextMinute } from './solar-clock';

describe('milliseconsUntilNextMinute', () => {
  it('waits only until the next UTC minute boundary', () => {
    const now = new Date('2026-06-21T12:34:12.345Z');

    expect(millisecondsUntilNextMinute(now)).toBe(47_655);
  });
  it('waits a full minute when called exactly on a minute boundary', () => {
    const now = new Date('2026-06-21T12:34:00.000Z');

    expect(millisecondsUntilNextMinute(now)).toBe(60_000);
  });
});
