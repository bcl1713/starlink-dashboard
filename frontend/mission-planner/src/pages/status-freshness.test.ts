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
  it('treats a sample five seconds old as stale', () => {
    const now = Date.parse('2026-09-07T12:00:05.000Z');

    expect(isStatusStale('2026-09-07T12:00:00.000Z', now)).toBe(true);
  });
});
