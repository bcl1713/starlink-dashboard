import { describe, expect, it } from 'vitest';

import type { MonitoringHistory } from '../../types/monitoring';
import {
  HISTORY_MAX_SAMPLES,
  alignPositionHistory,
  buildThroughputRenderSeries,
  mergeTimestampedSamples,
  summarizeLatency,
  summarizePacketLoss,
} from './history';

const deepFreeze = <T>(value: T): T => {
  if (value && typeof value === 'object') {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
};

const history = (series: MonitoringHistory['series']): MonitoringHistory => ({
  generated_at: '2026-08-29T12:30:00Z',
  window_start: '2026-08-29T12:00:00Z',
  window_end: '2026-08-29T12:30:00Z',
  range_seconds: 1800,
  step_seconds: 1,
  series,
});

describe('overview history utilities', () => {
  it('aligns latitude and longitude by exact represented instants', () => {
    const input = deepFreeze(
      history([
        {
          metric: 'latitude_degrees',
          samples: [
            { timestamp: 'bad', value: 44 },
            { timestamp: '2026-08-29T12:00:00.2Z', value: 91 },
            { timestamp: '2026-08-29T12:00:00.1Z', value: 39 },
            { timestamp: '2026-08-29T12:00:00.1000Z', value: null },
            { timestamp: '2026-08-29T07:00:01-05:00', value: 40 },
            { timestamp: '2026-08-29T12:00:01Z', value: 40.5 },
          ],
        },
        {
          metric: 'longitude_degrees',
          samples: [
            { timestamp: '2026-08-29T12:00:01Z', value: -105 },
            { timestamp: '2026-08-29T12:00:00.100Z', value: -181 },
            { timestamp: '2026-08-29T12:00:00.1000Z', value: -104 },
            { timestamp: '2026-08-29T12:00:01+00:00', value: null },
          ],
        },
      ])
    );
    const before = structuredClone(input);

    expect(alignPositionHistory(input)).toEqual([
      {
        timestamp: '2026-08-29T12:00:00.1Z',
        latitude: 39,
        longitude: -104,
        altitudeMeters: null,
      },
      {
        timestamp: '2026-08-29T12:00:01Z',
        latitude: 40.5,
        longitude: -105,
        altitudeMeters: null,
      },
    ]);
    expect(input).toEqual(before);
  });

  it('merges timestamped samples with closed windows, replacement, and caps', () => {
    const now = '2026-08-29T12:30:00.500Z';
    const lastGood = deepFreeze([
      { timestamp: '2026-08-29T11:59:59.499999Z', value: 1 },
      { timestamp: '2026-08-29T12:00:00.500Z', value: 2 },
      { timestamp: '2026-08-29T12:30:00.500Z', value: 3 },
      { timestamp: '2026-08-29T12:30:00.5001Z', value: 4 },
      { timestamp: '2026-08-29T12:10:00.1Z', value: 5 },
      { timestamp: '2026-08-29T12:10:00.1000Z', value: 6 },
    ]);
    const incoming = deepFreeze([
      { timestamp: 'not-a-date', value: 7 },
      { timestamp: '2026-08-29T12:10:00.10Z', value: null },
    ]);

    expect(mergeTimestampedSamples(lastGood, incoming, now)).toEqual([
      { timestamp: '2026-08-29T12:00:00.500Z', value: 2 },
      { timestamp: '2026-08-29T12:10:00.10Z', value: null },
      { timestamp: '2026-08-29T12:30:00.500Z', value: 3 },
    ]);

    const many = Array.from(
      { length: HISTORY_MAX_SAMPLES + 1 },
      (_, index) => ({
        timestamp: `2026-08-29T12:${String(Math.trunc(index / 60)).padStart(
          2,
          '0'
        )}:${String(index % 60).padStart(2, '0')}Z`,
        value: index,
      })
    );
    const capped = mergeTimestampedSamples([], many, '2026-08-29T12:30:01Z');
    expect(capped).toHaveLength(HISTORY_MAX_SAMPLES);
    expect(capped[0]).toEqual({ timestamp: '2026-08-29T12:00:01Z', value: 1 });
    expect(() =>
      mergeTimestampedSamples([], [], '2026-08-29T12:30:00')
    ).toThrow(RangeError);
  });

  it('summarizes latency and packet loss from valid samples in closed windows', () => {
    const samples = deepFreeze([
      { timestamp: '2026-08-29T12:24:59.999999Z', value: 9 },
      { timestamp: '2026-08-29T12:25:00Z', value: 100 },
      { timestamp: '2026-08-29T12:26:00Z', value: null },
      { timestamp: '2026-08-29T12:27:00Z', value: -1 },
      { timestamp: '2026-08-29T12:28:00Z', value: 200 },
      { timestamp: '2026-08-29T12:29:00Z', value: Number.POSITIVE_INFINITY },
      { timestamp: '2026-08-29T12:30:00.0000Z', value: 150 },
      { timestamp: '2026-08-29T12:30:00.0001Z', value: 300 },
    ]);

    expect(summarizeLatency(samples, '2026-08-29T12:30:00Z')).toEqual({
      available: true,
      current: 150,
      min: 100,
      mean: 150,
      max: 200,
      count: 3,
    });
    expect(summarizePacketLoss(samples, '2026-08-29T12:30:00Z', 120)).toEqual({
      available: false,
      current: null,
      min: null,
      mean: null,
      max: null,
      count: 0,
    });
    expect(() => summarizePacketLoss([], '2026-08-29T12:30:00Z', -1)).toThrow(
      RangeError
    );
  });

  it('handles exact fractional windows and finite summary arithmetic', () => {
    expect(
      summarizePacketLoss(
        [{ timestamp: '2026-08-29T11:59:59.99999995Z', value: 1 }],
        '2026-08-29T12:00:00Z',
        1e-7
      )
    ).toMatchObject({ available: true, current: 1, count: 1 });
    expect(
      summarizePacketLoss(
        [{ timestamp: '2026-08-29T12:00:00Z', value: 1 }],
        '2026-08-29T12:00:00Z',
        Number.MIN_VALUE
      )
    ).toMatchObject({ available: true, current: 1, count: 1 });
    const summary = summarizeLatency(
      [
        { timestamp: '2026-08-29T12:00:00Z', value: Number.MAX_VALUE },
        { timestamp: '2026-08-29T12:00:01Z', value: Number.MAX_VALUE },
        { timestamp: '2026-08-29T12:00:02Z', value: -0 },
      ],
      '2026-08-29T12:00:02Z'
    );
    expect(Number.isFinite(summary.mean)).toBe(true);
    expect(Object.is(summary.current, -0)).toBe(false);
    expect(Object.is(summary.min, -0)).toBe(false);
  });

  it('builds throughput union with sanitized null gaps and negated uploads', () => {
    const download = deepFreeze([
      { timestamp: '2026-08-29T12:00:00Z', value: 10 },
      { timestamp: '2026-08-29T12:00:01.1Z', value: 12 },
      { timestamp: '2026-08-29T12:00:01.1000Z', value: -1 },
    ]);
    const upload = deepFreeze([
      { timestamp: '2026-08-29T12:00:00+00:00', value: 0 },
      { timestamp: '2026-08-29T12:00:02Z', value: 4 },
      { timestamp: '2026-08-29T12:00:02.1Z', value: -4 },
    ]);

    const result = buildThroughputRenderSeries(download, upload);
    expect(result).toEqual([
      {
        timestamp: '2026-08-29T12:00:00Z',
        downloadMbps: 10,
        uploadMbps: 0,
      },
      {
        timestamp: '2026-08-29T12:00:01.1000Z',
        downloadMbps: null,
        uploadMbps: null,
      },
      {
        timestamp: '2026-08-29T12:00:02Z',
        downloadMbps: null,
        uploadMbps: -4,
      },
      {
        timestamp: '2026-08-29T12:00:02.1Z',
        downloadMbps: null,
        uploadMbps: null,
      },
    ]);
    expect(Object.is(result[0].uploadMbps, -0)).toBe(false);
  });
});
