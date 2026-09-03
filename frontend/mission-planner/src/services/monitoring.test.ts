import { describe, expect, it } from 'vitest';
import {
  groundEntryPointUrl,
  historyUrl,
  mapOverlayUrls,
  parseGroundEntryPoint,
  parseHistory,
  parseMapOverlays,
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

const maximumDefaultHistory = () => {
  const windowStart = '2026-09-02T11:30:00Z';
  const samples = Array.from({ length: 1801 }, (_, index) => ({
    timestamp: new Date(Date.parse(windowStart) + index * 1000).toISOString(),
    value: 0,
  }));
  return {
    generated_at: instant,
    window_start: windowStart,
    window_end: instant,
    range_seconds: 1800,
    step_seconds: 1,
    series: metrics.map((metric) => ({ metric, samples })),
  };
};

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
    expect([
      statusUrl,
      historyUrl,
      groundEntryPointUrl,
      poiUrl,
      ...mapOverlayUrls,
    ]).toEqual([
      '/api/status',
      '/api/monitoring/history',
      '/api/monitoring/ground-entry-point',
      '/api/pois/etas',
      '/api/route/coordinates/west',
      '/api/route/coordinates/east',
      '/api/active-x-link?state=normal',
      '/api/active-x-link?state=warning',
    ]);
    expect(parseStatus(status()).position.longitude).toBe(180);
  });

  it('keeps route and active-link map data bounded, validated, and IDL split', () => {
    const overlays = parseMapOverlays([
      {
        coordinates: [
          { latitude: 10, longitude: -180, altitude: 0, sequence: 0 },
        ],
        total: 1,
        route_id: 'route',
        route_name: 'Route',
      },
      {
        coordinates: [
          { latitude: 10, longitude: 180, altitude: 0, sequence: 1 },
        ],
        total: 1,
        route_id: 'route',
        route_name: 'Route',
      },
      {
        coordinates: [
          { latitude: 10, longitude: 179 },
          { latitude: 11, longitude: -179 },
        ],
        links: [],
        total: 2,
      },
      { coordinates: [], links: [], total: 0 },
    ]);

    expect(overlays.route.west).toEqual([[10, -180]]);
    expect(overlays.route.east).toEqual([[10, 180]]);
    expect(overlays.activeLinks.normal).toEqual({
      east: [
        [10, 179],
        [10.5, 180],
      ],
      west: [
        [10.5, -180],
        [11, -179],
      ],
    });
    expect(overlays.activeLinks.warning).toEqual({ east: [], west: [] });
    expect(() =>
      parseMapOverlays([
        {
          coordinates: Array.from({ length: 1001 }, () => ({
            latitude: 0,
            longitude: 0,
          })),
          total: 1001,
        },
        { coordinates: [], total: 0 },
        { coordinates: [], links: [], total: 0 },
        { coordinates: [], links: [], total: 0 },
      ])
    ).toThrow('Map response exceeds coordinate budget');
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

  it('enforces metric ranges and rejects the first over-limit cardinality', () => {
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
    ).toThrow('History response exceeds point budget');
  });

  it('accepts the maximum default six-series history response', () => {
    const parsed = parseHistory(maximumDefaultHistory());

    expect(parsed.series).toHaveLength(6);
    expect(
      parsed.series.every((series) => series.samples.length === 1801)
    ).toBe(true);
  });
});
