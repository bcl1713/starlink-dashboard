import { describe, expect, it, vi } from 'vitest';
import { parseGroundEntryPoint, parseHistory, parseStatus } from './monitoring';

const metrics = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

const statusAt = (timestamp: string) => ({
  source: 'live',
  timestamp,
  observed_at: timestamp,
  received_at: timestamp,
  position: {
    latitude: 0,
    longitude: 0,
    altitude: 1,
    speed: 0,
    heading: 0,
  },
  network: {
    latency_ms: 1,
    throughput_down_mbps: 1,
    throughput_up_mbps: 1,
    packet_loss_percent: 0,
  },
  obstruction: { obstruction_percent: 0 },
  environmental: {
    signal_quality_percent: 100,
    uptime_seconds: 1,
    temperature_celsius: null,
  },
});

const historyAt = (timestamp: string) => ({
  generated_at: timestamp,
  window_start: '2026-09-02T11:59:00.000001+00:00',
  window_end: timestamp,
  range_seconds: 60,
  step_seconds: 1,
  series: metrics.map((metric) => ({
    metric,
    samples: [{ timestamp, value: 0 }],
  })),
});

const gepAt = (timestamp: string) => ({
  available: true,
  observed_at: timestamp,
  generated_at: timestamp,
  display: 'Omaha',
  city: 'Omaha',
  region: 'Nebraska',
  country: 'US',
  latitude: 41,
  longitude: -96,
});

describe('monitoring timestamp input bounds', () => {
  it.each(['', '.1', '.12', '.123', '.1234', '.12345', '.123456'])(
    'accepts producer precision in %s form',
    (fraction) => {
      const timestamp = `2026-09-02T12:00:00${fraction}Z`;
      expect(parseStatus(statusAt(timestamp)).observed_at).toBe(timestamp);
    }
  );

  it.each([
    '0001-01-01T00:00:00.000001+00:00',
    '9999-12-31T23:59:59.999999+00:00',
    '2026-09-02T12:00:00.000001+23:59',
    '2026-09-02T12:00:00.000001-23:59',
  ])('preserves supported year and offset boundary %s', (timestamp) => {
    expect(parseStatus(statusAt(timestamp)).observed_at).toBe(timestamp);
  });

  it('accepts maximum-width timestamps in status, history samples, and GEP', () => {
    const timestamp = '2026-09-02T12:00:00.000001+00:00';
    expect(parseStatus(statusAt(timestamp)).observed_at).toBe(timestamp);
    expect(
      parseHistory(historyAt(timestamp)).series[0].samples[0].timestamp
    ).toBe(timestamp);
    expect(parseGroundEntryPoint(gepAt(timestamp)).generated_at).toBe(
      timestamp
    );
  });

  it('rejects seven fractional digits in status, history, samples, and GEP', () => {
    const valid = '2026-09-02T12:00:00.000001Z';
    const overPrecision = '2026-09-02T12:00:00.0000010Z';
    expect(() =>
      parseStatus({ ...statusAt(valid), received_at: overPrecision })
    ).toThrow();
    expect(() =>
      parseHistory({ ...historyAt(valid), generated_at: overPrecision })
    ).toThrow();
    const invalidSample = historyAt(valid);
    invalidSample.series[0].samples[0].timestamp = overPrecision;
    expect(() => parseHistory(invalidSample)).toThrow();
    expect(() =>
      parseGroundEntryPoint({ ...gepAt(valid), generated_at: overPrecision })
    ).toThrow();
  });

  it('rejects a huge fraction before constructing a huge BigInt', () => {
    const bigInt = vi.spyOn(globalThis, 'BigInt');
    const valid = '2026-09-02T12:00:00.000001Z';
    const oversized = `2026-09-02T12:00:00.${'1'.repeat(100_000)}Z`;

    try {
      expect(() =>
        parseStatus({ ...statusAt(valid), received_at: oversized })
      ).toThrow();
      expect(
        bigInt.mock.calls.some(
          ([argument]) => typeof argument === 'string' && argument.length > 6
        )
      ).toBe(false);
    } finally {
      bigInt.mockRestore();
    }
  });
});
