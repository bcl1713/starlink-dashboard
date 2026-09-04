import { describe, expect, it } from 'vitest';
import { parseGroundEntryPoint, parseHistory, parseStatus } from './monitoring';

const observed = '2026-09-02T12:00:00.000001Z';
const metrics = [
  'latitude_degrees',
  'longitude_degrees',
  'latency_ms',
  'throughput_down_mbps',
  'throughput_up_mbps',
  'packet_loss_percent',
] as const;

const status = () => ({
  source: 'live',
  timestamp: observed,
  observed_at: observed,
  received_at: observed,
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

const history = () => ({
  generated_at: '2026-09-02T12:00:00.000001Z',
  window_start: '2026-09-02T11:59:00.000001Z',
  window_end: '2026-09-02T12:00:00.000001Z',
  range_seconds: 60,
  step_seconds: 1,
  series: metrics.map((metric) => ({
    metric,
    samples: [{ timestamp: observed, value: 0 }],
  })),
});

const withFirstSamples = (
  samples: Array<{ timestamp: string; value: number }>
) => ({
  ...history(),
  series: history().series.map((series, index) =>
    index === 0 ? { ...series, samples } : series
  ),
});

const gep = () => ({
  available: true,
  observed_at: observed,
  generated_at: observed,
  display: 'Omaha',
  city: 'Omaha',
  region: 'Nebraska',
  country: 'US',
  latitude: 41,
  longitude: -96,
});

describe('monitoring instant precision', () => {
  it('rejects a legacy status timestamp one microsecond before observation', () => {
    expect(() =>
      parseStatus({ ...status(), timestamp: '2026-09-02T12:00:00.000000Z' })
    ).toThrow('legacy timestamp differs from observation');
  });

  it('accepts timezone-equivalent legacy timestamps at full precision', () => {
    expect(
      parseStatus({
        ...status(),
        timestamp: '2026-09-02T13:00:00.000001+01:00',
      }).observed_at
    ).toBe(observed);
  });

  it('rejects receipt one microsecond before observation', () => {
    expect(() =>
      parseStatus({ ...status(), received_at: '2026-09-02T12:00:00.000000Z' })
    ).toThrow('receipt precedes observation');
  });

  it('accepts receipt exactly at the observation boundary', () => {
    expect(parseStatus(status()).received_at).toBe(observed);
  });

  it('rejects a history start one microsecond after its end', () => {
    const value = {
      ...history(),
      window_start: '2026-09-02T12:00:00.000002Z',
    };
    expect(() => parseHistory(value)).toThrow('invalid history window');
  });

  it('rejects a history duration one microsecond longer than its integer range', () => {
    const value = {
      ...history(),
      window_end: '2026-09-02T12:00:00.000002Z',
      generated_at: '2026-09-02T12:00:00.000002Z',
    };
    expect(() => parseHistory(value)).toThrow(
      'history range disagrees with window'
    );
  });

  it('accepts an exact integer history duration across equivalent offsets', () => {
    const value = {
      ...history(),
      window_start: '2026-09-02T12:59:00.000001+01:00',
      window_end: '2026-09-02T13:00:00.000001+01:00',
      generated_at: '2026-09-02T13:00:00.000001+01:00',
    };
    expect(parseHistory(value).range_seconds).toBe(60);
  });

  it('rejects history generation one microsecond before window end', () => {
    expect(() =>
      parseHistory({
        ...history(),
        generated_at: '2026-09-02T12:00:00.000000Z',
      })
    ).toThrow('history generation precedes window end');
  });

  it('rejects a sample one microsecond before the history window', () => {
    expect(() =>
      parseHistory(
        withFirstSamples([
          { timestamp: '2026-09-02T11:59:00.000000Z', value: 0 },
        ])
      )
    ).toThrow('invalid history sample timestamp');
  });

  it('rejects a sample one microsecond after the history window', () => {
    expect(() =>
      parseHistory(
        withFirstSamples([
          { timestamp: '2026-09-02T12:00:00.000002Z', value: 0 },
        ])
      )
    ).toThrow('invalid history sample timestamp');
  });

  it('rejects samples descending by one microsecond', () => {
    expect(() =>
      parseHistory(
        withFirstSamples([
          { timestamp: '2026-09-02T12:00:00.000001Z', value: 0 },
          { timestamp: '2026-09-02T12:00:00.000000Z', value: 0 },
        ])
      )
    ).toThrow('invalid history sample timestamp');
  });

  it('accepts samples ascending by one microsecond', () => {
    const samples = [
      { timestamp: '2026-09-02T12:00:00.000000Z', value: 0 },
      { timestamp: '2026-09-02T12:00:00.000001Z', value: 0 },
    ];
    expect(parseHistory(withFirstSamples(samples)).series[0].samples).toEqual(
      samples
    );
  });

  it('accepts samples at both inclusive window boundaries', () => {
    const samples = [
      { timestamp: '2026-09-02T11:59:00.000001Z', value: 0 },
      { timestamp: '2026-09-02T12:00:00.000001Z', value: 0 },
    ];
    expect(parseHistory(withFirstSamples(samples)).series[0].samples).toEqual(
      samples
    );
  });

  it('rejects a GEP observation one microsecond after generation', () => {
    expect(() =>
      parseGroundEntryPoint({
        ...gep(),
        observed_at: '2026-09-02T12:00:00.000002Z',
      })
    ).toThrow('GEP observation follows generation');
  });

  it('accepts a GEP observation exactly at generation in another offset', () => {
    const value = {
      ...gep(),
      observed_at: '2026-09-02T13:00:00.000001+01:00',
    };
    expect(parseGroundEntryPoint(value).observed_at).toBe(value.observed_at);
  });
});
