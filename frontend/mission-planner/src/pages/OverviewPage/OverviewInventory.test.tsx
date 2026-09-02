import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { CurrentPositionMap } from './CurrentPositionMap';
import { OverviewInventory } from './OverviewInventory';

const sourceState = {
  loading: false,
  stale: false,
  error: null,
  lastSuccess: new Date('2026-09-02T12:00:00Z'),
  recovering: false,
  recoveredAt: null,
};

const status = {
  source: 'simulation' as const,
  timestamp: '2026-09-02T12:00:00Z',
  observed_at: '2026-09-02T12:00:00Z',
  received_at: '2026-09-02T12:00:01Z',
  position: { latitude: 0, longitude: 180, altitude: 1, speed: 0, heading: 0 },
  network: {
    latency_ms: 20,
    throughput_down_mbps: 100,
    throughput_up_mbps: 10,
    packet_loss_percent: 1,
  },
  obstruction: { obstruction_percent: 2 },
  environmental: {
    signal_quality_percent: 99,
    uptime_seconds: 10,
    temperature_celsius: null,
  },
};

describe('OverviewInventory', () => {
  it('supplies the required operational inventory without fullscreen layout', () => {
    const html = renderToStaticMarkup(
      <OverviewInventory
        status={status}
        statusMessage="Updated 12:00:01"
        latency={{ current: 999, min: 10, average: 504.5, max: 999 }}
        packetLoss={{ current: 99, min: 0, average: 49.5, max: 99 }}
        gep={null}
        gepState={sourceState}
        refreshGep={async () => {}}
        pois={[]}
        poiState={sourceState}
        refreshPois={async () => {}}
        cadence={1}
        now={new Date('2026-09-02T12:00:00Z')}
      />
    );

    expect(html.match(/data-clock=/g) ?? []).toHaveLength(4);
    expect(html).toContain('Current position map');
    expect(html).toContain('Top applicable POIs');
    expect(html).toContain('5-minute min / avg / max');
    expect(html).toContain('20.0 ms');
    expect(html).toContain('999.0 ms');
    expect(html).toContain('1.0%');
    expect(html).toContain('99.0%');
    expect(html).toContain('<svg');
    expect(html).toContain('Current position: 0.0000, -180.0000');
    expect(html).toContain('Download');
    expect(html).toContain('Upload');
    expect(html).toContain('Ground entry point');
    expect(html).toContain('Obstruction');
    expect(html).toContain('Packet loss');
    expect(html).toContain('Selected interval');
    expect(html).not.toContain('Grafana');
  });

  it('normalizes IDL coordinates and rejects nonfinite map input', () => {
    const normalized = renderToStaticMarkup(
      <CurrentPositionMap latitude={10} longitude={540} />
    );
    const rejected = renderToStaticMarkup(
      <CurrentPositionMap latitude={Number.POSITIVE_INFINITY} longitude={0} />
    );

    expect(normalized).toContain('Current position: 10.0000, -180.0000');
    expect(rejected).toContain('Position unavailable');
    expect(rejected).not.toContain('<svg');
  });
});
