import { describe, expect, it } from 'vitest';
import {
  groundEntryPointUrl,
  historyUrl,
  parseGroundEntryPoint,
  parseHistory,
  parseStatus,
  poiUrl,
  statusUrl,
} from './monitoring';

const instant = '2026-09-02T12:00:00Z';
const later = '2026-09-02T12:00:01Z';
const historyStart = '2026-09-02T11:59:01Z';
const status = () => ({
  source: 'live',
  timestamp: instant,
  observed_at: instant,
  received_at: later,
  position: {
    latitude: 0,
    longitude: 180,
    altitude: 1,
    speed: 0,
    heading: 360,
  },
  network: {
    latency_ms: 10,
    throughput_down_mbps: 20,
    throughput_up_mbps: 3,
    packet_loss_percent: 0,
  },
  obstruction: { obstruction_percent: 0 },
  environmental: {
    signal_quality_percent: 100,
    uptime_seconds: 1,
    temperature_celsius: null,
  },
});

const metrics = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

const history = () => ({
  generated_at: later,
  window_start: historyStart,
  window_end: later,
  range_seconds: 60,
  step_seconds: 1,
  series: metrics.map((metric) => ({
    metric,
    samples: [{ timestamp: instant, value: 0 }],
  })),
});

const gep = () => ({
  available: true,
  observed_at: instant,
  generated_at: later,
  display: '<b>Omaha</b>',
  city: 'Omaha',
  region: 'Nebraska',
  country: 'US',
  latitude: 41,
  longitude: -96,
});

describe('monitoring service contracts', () => {
  it('uses only origin-relative monitoring URLs', () => {
    expect([statusUrl, historyUrl, groundEntryPointUrl, poiUrl]).toEqual([
      '/api/status',
      '/api/monitoring/history',
      '/api/monitoring/ground-entry-point',
      '/api/pois/etas',
    ]);
    expect(parseStatus(status()).position.longitude).toBe(180);
  });

  it('rejects unknown fields at every status nesting level', () => {
    expect(() => parseStatus({ ...status(), extra: true })).toThrow();
    expect(() =>
      parseStatus({
        ...status(),
        position: { ...status().position, extra: true },
      })
    ).toThrow();
    expect(() =>
      parseStatus({
        ...status(),
        network: { ...status().network, extra: true },
      })
    ).toThrow();
    expect(() =>
      parseStatus({
        ...status(),
        obstruction: { ...status().obstruction, extra: true },
      })
    ).toThrow();
    expect(() =>
      parseStatus({
        ...status(),
        environmental: { ...status().environmental, extra: true },
      })
    ).toThrow();
  });

  it('rejects nonfinite status and receipt before observation', () => {
    expect(() =>
      parseStatus({
        ...status(),
        network: { ...status().network, latency_ms: Infinity },
      })
    ).toThrow();
    expect(() =>
      parseStatus({
        ...status(),
        observed_at: later,
        received_at: instant,
      })
    ).toThrow();
  });

  it('requires status timestamps to be coherent instants', () => {
    expect(() =>
      parseStatus({
        ...status(),
        timestamp: '2026-09-02T11:00:00Z',
      })
    ).toThrow();
    expect(
      parseStatus({
        ...status(),
        timestamp: '2026-09-02T13:00:00+01:00',
      }).observed_at
    ).toBe(instant);
    expect(() =>
      parseStatus({
        ...status(),
        received_at: '2026-09-02T11:59:59.999Z',
      })
    ).toThrow();
  });

  it('requires exact history range and generation coherence', () => {
    expect(() => parseHistory({ ...history(), range_seconds: 61 })).toThrow();
    expect(() =>
      parseHistory({ ...history(), generated_at: instant })
    ).toThrow();
    expect(
      parseHistory({
        ...history(),
        window_start: '2026-09-02T12:59:01+01:00',
        window_end: '2026-09-02T13:00:01+01:00',
        generated_at: '2026-09-02T13:00:01+01:00',
      }).range_seconds
    ).toBe(60);
  });

  it('requires non-null GEP observations not to follow generation', () => {
    expect(() =>
      parseGroundEntryPoint({
        ...gep(),
        observed_at: '2026-09-02T12:00:02Z',
      })
    ).toThrow();
    expect(
      parseGroundEntryPoint({
        ...gep(),
        observed_at: '2026-09-02T13:00:01+01:00',
      }).observed_at
    ).toBe('2026-09-02T13:00:01+01:00');
    expect(
      parseGroundEntryPoint({ ...gep(), available: false, observed_at: null })
        .observed_at
    ).toBeNull();
  });

  it('rejects unknown fields and IPs in GEP DTOs', () => {
    expect(() =>
      parseGroundEntryPoint({ ...gep(), ip: '203.0.113.8' })
    ).toThrow();
    expect(() => parseGroundEntryPoint({ ...gep(), extra: true })).toThrow();
  });

  it('bounds GEP external strings', () => {
    expect(() =>
      parseGroundEntryPoint({ ...gep(), display: 'x'.repeat(201) })
    ).toThrow();
  });

  it('requires a coherent window and exact canonical history series', () => {
    expect(() =>
      parseHistory({ ...history(), window_start: later, window_end: instant })
    ).toThrow();
    expect(() => parseHistory({ ...history(), series: [] })).toThrow();
    const reversed = [...history().series].reverse();
    expect(() => parseHistory({ ...history(), series: reversed })).toThrow();
    expect(() =>
      parseHistory({
        ...history(),
        series: history().series.map((series, index) =>
          index === 1 ? { ...series, metric: 'latitude_degrees' } : series
        ),
      })
    ).toThrow();
  });

  it('rejects unknown, descending, duplicate, and out-of-window samples', () => {
    const invalidSamples = [
      [{ timestamp: instant, value: 0, extra: true }],
      [
        { timestamp: later, value: 0 },
        { timestamp: instant, value: 0 },
      ],
      [
        { timestamp: instant, value: 0 },
        { timestamp: instant, value: 1 },
      ],
      [{ timestamp: '2026-09-02T11:59:00Z', value: 0 }],
    ];
    for (const samples of invalidSamples) {
      const series = history().series.map((item, index) =>
        index === 0 ? { ...item, samples } : item
      );
      expect(() => parseHistory({ ...history(), series })).toThrow();
    }
  });

  it('enforces metric ranges plus per-series and aggregate point budgets', () => {
    const invalidRanges = [-91, -181, -1, -1, -1, 101];
    invalidRanges.forEach((value, index) => {
      const series = history().series.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, samples: [{ timestamp: instant, value }] }
          : item
      );
      expect(() => parseHistory({ ...history(), series })).toThrow();
    });

    const many = Array.from({ length: 1802 }, (_, index) => ({
      timestamp: new Date(Date.parse(instant) + index / 10).toISOString(),
      value: 0,
    }));
    expect(() =>
      parseHistory({
        ...history(),
        series: history().series.map((item, index) =>
          index === 0 ? { ...item, samples: many } : item
        ),
      })
    ).toThrow();

    const aggregate = Array.from({ length: 1201 }, (_, index) => ({
      timestamp: new Date(Date.parse(instant) + index / 2).toISOString(),
      value: 0,
    }));
    expect(() =>
      parseHistory({
        ...history(),
        window_end: '2026-09-02T12:10:01Z',
        series: history().series.map((item) => ({
          ...item,
          samples: aggregate,
        })),
      })
    ).toThrow();
  });
});
