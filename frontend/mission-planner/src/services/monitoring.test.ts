import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  groundEntryPointUrl,
  getJson,
  historyUrl,
  parseApplicablePois,
  parseGroundEntryPoint,
  parseHistory,
  parseStatus,
  poiUrl,
  statusUrl,
} from './monitoring';

const instant = '2026-09-02T12:00:00Z';
const later = '2026-09-02T12:00:01Z';
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
  window_start: instant,
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

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
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

  it('aborts a production JSON request at the four-second bound', async () => {
    vi.useFakeTimers();
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string | URL | Request, init?: RequestInit) => {
        requestSignal = init?.signal ?? undefined;
        return new Promise<Response>((_resolve, reject) => {
          requestSignal?.addEventListener('abort', () =>
            reject(new Error('aborted'))
          );
        });
      })
    );

    const request = getJson('/api/status');
    const rejection = expect(request).rejects.toThrow('aborted');
    await vi.advanceTimersByTimeAsync(3999);
    expect(requestSignal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expect(requestSignal?.aborted).toBe(true);
    await rejection;
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

  it('bounds and strictly validates the external POI collection', () => {
    const poi = {
      poi_id: 'poi-1',
      name: 'Airport',
      category: null,
      eta_seconds: 60,
      distance_meters: 1000,
      active: true,
      latitude: 41,
      longitude: -96,
    };
    expect(() =>
      parseApplicablePois({ pois: [{ ...poi, extra: true }] })
    ).toThrow();
    expect(() =>
      parseApplicablePois({ pois: [{ ...poi, name: 'x'.repeat(201) }] })
    ).toThrow();
    expect(() =>
      parseApplicablePois({ pois: Array.from({ length: 101 }, () => poi) })
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
      [{ timestamp: '2026-09-02T11:59:59Z', value: 0 }],
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
