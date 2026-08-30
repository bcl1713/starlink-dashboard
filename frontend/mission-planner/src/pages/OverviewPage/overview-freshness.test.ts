import { describe, expect, it } from 'vitest';

import { compareAwareTimestampToEpochMilliseconds } from '../../services/monitoring-validation';
import {
  classifyOverviewError,
  computeSourceFreshness,
  radarTimestampFromFrame,
} from './overview-freshness';

describe('overview freshness', () => {
  it('compares aware timestamps to epochs exactly across offsets and fractions', () => {
    expect(
      compareAwareTimestampToEpochMilliseconds(
        '2026-08-29T06:00:00.000000000000Z',
        1_787_983_200_000
      )
    ).toBe(0);
    expect(
      compareAwareTimestampToEpochMilliseconds(
        '2026-08-29T01:00:00.000000000001-05:00',
        1_787_983_200_000
      )
    ).toBe(1);
    expect(
      compareAwareTimestampToEpochMilliseconds(
        '0000-01-01T00:00:00Z',
        0,
        -62_167_219_200
      )
    ).toBe(0);
    expect(
      compareAwareTimestampToEpochMilliseconds('2026-02-30T00:00:00Z', 0)
    ).toBeNull();
    expect(
      compareAwareTimestampToEpochMilliseconds(
        '2026-08-29T06:00:00Z',
        Number.MAX_SAFE_INTEGER + 1
      )
    ).toBeNull();
  });

  it('classifies fresh, stale, future-tolerated, and unknown source timestamps', () => {
    expect(
      computeSourceFreshness('2026-08-29T12:00:05Z', 1_788_004_800_000, 1)
    ).toEqual({ freshness: 'fresh', ageSeconds: 0 });
    expect(
      computeSourceFreshness('2026-08-29T12:00:06Z', 1_788_004_800_000, 1)
    ).toEqual({ freshness: 'unknown', ageSeconds: null });
    expect(
      computeSourceFreshness('2026-08-29T11:59:55Z', 1_788_004_800_000, 1)
    ).toEqual({ freshness: 'fresh', ageSeconds: 5 });
    expect(
      computeSourceFreshness(
        '2026-08-29T11:59:54.999999999Z',
        1_788_004_800_000,
        1
      )
    ).toEqual({ freshness: 'stale', ageSeconds: 5 });
    expect(computeSourceFreshness(null, 1_788_004_800_000, 30)).toEqual({
      freshness: 'unknown',
      ageSeconds: null,
    });
  });

  it('accepts only safe unix-second radar frame strings', () => {
    expect(radarTimestampFromFrame('946684800')).toBe('2000-01-01T00:00:00Z');
    expect(radarTimestampFromFrame('4102444800')).toBe('2100-01-01T00:00:00Z');
    expect(radarTimestampFromFrame('0946684800')).toBeNull();
    expect(radarTimestampFromFrame('4102444801')).toBeNull();
  });

  it('sanitizes cancellation, validation, and hostile request errors', () => {
    const validation = {
      name: 'OverviewDataValidationError',
      code: 'invalid_overview_data',
      source: 'status',
    };
    expect(classifyOverviewError(validation, false)).toEqual({
      code: 'invalid-data',
      message: 'Source data was invalid.',
    });
    expect(classifyOverviewError(new Error('boom'), false)).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
    expect(classifyOverviewError(new Error('aborted'), true)).toBeNull();
    const hostile = new Proxy(
      {},
      {
        get() {
          throw new Error('trap');
        },
      }
    );
    expect(classifyOverviewError(hostile, false)).toEqual({
      code: 'request-failed',
      message: 'Source refresh failed.',
    });
  });
});
