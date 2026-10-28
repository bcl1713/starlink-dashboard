import { expect, it } from 'vitest';
import { revisionUtc } from './revisionUtc';
it('labels UTC history Zulu while preserving its calendar and fractional evidence', () => {
  expect(revisionUtc('2026-10-17T10:11:12.123456Z')).toBe(
    '2026-10-17 10:11:12.123456 Zulu'
  );
  expect(revisionUtc(null)).toBe('Unknown');
});
