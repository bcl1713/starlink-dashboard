import { describe, expect, it } from 'vitest';

import { awareTimestampToChartEpochSeconds } from '../../../services/monitoring-validation';

describe('awareTimestampToChartEpochSeconds', () => {
  it('does not expose structurally forgeable parsed instants publicly', async () => {
    const exported = await import('../../../services/monitoring-validation');

    expect(Object.keys(exported).sort()).toEqual([
      'awareTimestampSchema',
      'awareTimestampToChartEpochSeconds',
      'azimuthSchema',
      'compareAwareTimestampInstants',
      'compareAwareTimestampToEpochMilliseconds',
      'finiteNumberSchema',
      'isStrictlyChronological',
      'latitudeSchema',
      'longitudeSchema',
      'nonNegativeNumberSchema',
      'percentSchema',
    ]);
  });

  it('projects accepted aware timestamps to finite Unix seconds', () => {
    expect(awareTimestampToChartEpochSeconds('1970-01-01T00:00:00Z')).toBe(0);
    expect(awareTimestampToChartEpochSeconds('1970-01-01T00:00:00.5Z')).toBe(
      0.5
    );
    expect(awareTimestampToChartEpochSeconds('2026-08-29T12:00:00+01:30')).toBe(
      1_787_999_400
    );
    expect(awareTimestampToChartEpochSeconds('0000-02-29T00:00:00Z')).toBe(
      -62_162_121_600
    );
    expect(awareTimestampToChartEpochSeconds('9999-12-31T23:59:59Z')).toBe(
      253_402_300_799
    );
  });

  it('rejects malformed, non-calendar, expanded-year, and TimeClip values', () => {
    expect(awareTimestampToChartEpochSeconds('2026-08-29T12:00:00')).toBeNull();
    expect(
      awareTimestampToChartEpochSeconds('+2026-08-29T12:00:00Z')
    ).toBeNull();
    expect(
      awareTimestampToChartEpochSeconds('2026-02-29T12:00:00Z')
    ).toBeNull();
    expect(
      awareTimestampToChartEpochSeconds('2026-08-29T12:00:00+24:00')
    ).toBeNull();
    expect(
      awareTimestampToChartEpochSeconds('275760-09-13T00:00:00Z')
    ).toBeNull();
  });

  it('is total for hostile JavaScript callers and large accepted fractions', () => {
    expect(
      awareTimestampToChartEpochSeconds(null as unknown as string)
    ).toBeNull();
    expect(
      awareTimestampToChartEpochSeconds(
        `2026-08-29T12:00:00.${'1'.repeat(100_000)}Z`
      )
    ).toBe(1_788_004_800.1111112);
  });
});
