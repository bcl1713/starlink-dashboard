import { describe, expect, it } from 'vitest';
import { parseGroundEntryPoint, parseStatus, statusUrl } from './monitoring';

describe('monitoring service contracts', () => {
  it('uses a same-origin status URL and accepts finite IDL coordinates', () => {
    expect(statusUrl).toBe('/api/status');
    const result = parseStatus({
      source: 'live',
      timestamp: '2026-09-02T12:00:00Z',
      observed_at: '2026-09-02T12:00:00Z',
      received_at: '2026-09-02T12:00:01Z',
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
    expect(result.position.longitude).toBe(180);
  });

  it('rejects nonfinite status and strips any GEP IP field', () => {
    expect(() =>
      parseStatus({
        network: { latency_ms: Number.POSITIVE_INFINITY },
      })
    ).toThrow();
    const gep = parseGroundEntryPoint({
      available: true,
      observed_at: '2026-09-02T12:00:00Z',
      generated_at: '2026-09-02T12:00:01Z',
      display: '<b>Omaha</b>',
      city: 'Omaha',
      region: 'Nebraska',
      country: 'US',
      latitude: 41,
      longitude: -96,
      ip: '203.0.113.8',
    });
    expect(gep).not.toHaveProperty('ip');
    expect(gep.display).toBe('<b>Omaha</b>');
  });
});
