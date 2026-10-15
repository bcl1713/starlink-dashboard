import { describe, expect, it } from 'vitest';
import { isStatusStale } from './status-freshness';

describe('status-freshness', () => {
  it('treats a recent status sample as fresh', () => {
    const now = Date.parse('2026-09-07T12:00:05.000Z');

    expect(isStatusStale('2026-09-07T12:00:01.000Z', now)).toBe(false);
  });
  it('treats an unparseable timestamp as stale', () => {
    const now = Date.parse('2026-09-07T12:00:05.000Z');

    expect(isStatusStale('not-a-timestamp', now)).toBe(true);
  });
  it('allows collection and polling delay before the ten-second cutoff', () => {
    const now = Date.parse('2026-09-07T12:00:09.999Z');

    expect(isStatusStale('2026-09-07T12:00:00.000Z', now)).toBe(false);
    expect(isStatusStale('2026-09-07T12:00:00.000Z', now + 1)).toBe(true);
  });
  it('allows small clock skew and observations after the latest render tick', () => {
    const now = Date.parse('2026-09-07T12:00:00.000Z');

    expect(isStatusStale('2026-09-07T12:00:00.999Z', now)).toBe(false);
    expect(isStatusStale('2026-09-07T12:00:05.000Z', now)).toBe(false);
    expect(isStatusStale('2026-09-07T12:00:05.001Z', now)).toBe(true);
  });
  it.each([NaN, Infinity, -Infinity])(
    'fails closed for invalid clock %s',
    (now) => {
      expect(isStatusStale('2026-09-07T12:00:00.000Z', now)).toBe(true);
    }
  );
});
