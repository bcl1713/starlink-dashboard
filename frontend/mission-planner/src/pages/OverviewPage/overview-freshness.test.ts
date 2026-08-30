import { describe, expect, it } from 'vitest';

import { compareAwareTimestampToEpochMilliseconds } from '../../services/monitoring-validation';
import {
  classifyOverviewError,
  computeFreshnessForSource,
  radarTimestampFromFrame,
  semanticUnavailable,
  sourceTimestamp,
} from './overview-freshness';
import {
  activeXLinkPayload,
  availableGep,
  historyPayload,
  poiPayload,
  routePayload,
  statusPayload,
  unavailableGep,
} from '../../services/monitoring-test-fixtures';

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
      computeFreshnessForSource(
        '',
        '2026-08-29T12:00:05Z',
        1_788_004_800_000,
        1
      )
    ).toEqual({ freshness: 'fresh', ageSeconds: 0 });
    expect(
      computeFreshnessForSource(
        '',
        '2026-08-29T12:00:06Z',
        1_788_004_800_000,
        1
      )
    ).toEqual({ freshness: 'unknown', ageSeconds: null });
    expect(
      computeFreshnessForSource(
        '',
        '2026-08-29T11:59:55Z',
        1_788_004_800_000,
        1
      )
    ).toEqual({ freshness: 'fresh', ageSeconds: 5 });
    expect(
      computeFreshnessForSource(
        '',
        '2026-08-29T11:59:54.999999999Z',
        1_788_004_800_000,
        1
      )
    ).toEqual({ freshness: 'stale', ageSeconds: 5 });
    expect(computeFreshnessForSource('', null, 1_788_004_800_000, 30)).toEqual({
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

  it('extracts timestamps for all canonical freshness sources', () => {
    expect(sourceTimestamp('telemetry', statusPayload)).toBe(
      statusPayload.timestamp
    );
    expect(sourceTimestamp('pois', poiPayload)).toBe(poiPayload.timestamp);
    expect(sourceTimestamp('satellites', poiPayload)).toBe(
      poiPayload.timestamp
    );
    expect(sourceTimestamp('missionEvents', poiPayload)).toBe(
      poiPayload.timestamp
    );
    expect(
      sourceTimestamp('groundEntryPoint', {
        ...availableGep,
        observed_at: '2026-08-29T12:00:00Z',
      })
    ).toBe('2026-08-29T12:00:00Z');
    expect(sourceTimestamp('radar', { frameTimestamp: '946684800' })).toBe(
      '946684800'
    );
  });

  it('uses grouped older timestamps, tie order, and null propagation', () => {
    expect(
      sourceTimestamp('activeLink', {
        normal: {
          ...activeXLinkPayload,
          observed_at: '2026-08-29T12:00:00Z',
        },
        warning: {
          ...activeXLinkPayload,
          observed_at: '2026-08-29T12:00:01Z',
        },
      })
    ).toBe('2026-08-29T12:00:00Z');
    expect(
      sourceTimestamp('route', {
        west: { ...routePayload, revision_at: '2026-08-29T12:00:00Z' },
        east: { ...routePayload, revision_at: '2026-08-29T12:00:00Z' },
      })
    ).toBe('2026-08-29T12:00:00Z');
    expect(
      sourceTimestamp('activeLink', {
        normal: { ...activeXLinkPayload, observed_at: null },
        warning: {
          ...activeXLinkPayload,
          observed_at: '2026-08-29T12:00:00Z',
        },
      })
    ).toBeNull();
    expect(sourceTimestamp('groundEntryPoint', unavailableGep)).toBeNull();
  });

  it('uses the oldest latest history metric and preserves canonical tie text', () => {
    const history = {
      ...historyPayload,
      series: historyPayload.series.map((series, index) => ({
        ...series,
        samples: [
          {
            timestamp:
              index === 0
                ? '2026-08-29T07:00:00-05:00'
                : '2026-08-29T12:00:00Z',
            value: index,
          },
          { timestamp: '2026-08-29T12:00:01Z', value: index },
        ],
      })),
    };
    expect(sourceTimestamp('history', history)).toBe('2026-08-29T12:00:01Z');
    expect(
      sourceTimestamp('history', {
        ...history,
        series: history.series.map((series) => ({ ...series, samples: [] })),
      })
    ).toBeNull();
  });

  it('detects route and GEP semantic unavailable states', () => {
    expect(semanticUnavailable('groundEntryPoint', unavailableGep)).toBe(true);
    expect(
      semanticUnavailable('route', {
        west: { ...routePayload, route_id: null, total: 0 },
        east: { ...routePayload, route_id: null, total: 0 },
      })
    ).toBe(true);
    expect(
      semanticUnavailable('route', {
        west: routePayload,
        east: routePayload,
      })
    ).toBe(false);
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
