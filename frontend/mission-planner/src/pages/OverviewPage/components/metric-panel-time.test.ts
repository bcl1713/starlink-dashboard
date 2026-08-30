import { describe, expect, it } from 'vitest';

import { formatUtcTimestamp } from './metric-panel-time';

describe('formatUtcTimestamp', () => {
  it('renders accepted years 0000-0099 with offsets in UTC', () => {
    expect(formatUtcTimestamp('0000-01-01T01:30:00+01:30')).toBe(
      '0000-01-01 00:00:00 UTC'
    );
    expect(formatUtcTimestamp('0099-01-01T00:00:00+01:00')).toBe(
      '0098-12-31 23:00:00 UTC'
    );
  });

  it('renders accepted year zero lower-bound crossings with signed UTC years', () => {
    expect(formatUtcTimestamp('0000-01-01T00:00:00+01:00')).toBe(
      '-0001-12-31 23:00:00 UTC'
    );
  });

  it('rejects malformed and non-calendar timestamps without trusting Date', () => {
    expect(formatUtcTimestamp('2026-02-29T00:00:00Z')).toBe('Unavailable');
    expect(formatUtcTimestamp('2026-01-01T00:00:00+24:00')).toBe('Unavailable');
  });
});
