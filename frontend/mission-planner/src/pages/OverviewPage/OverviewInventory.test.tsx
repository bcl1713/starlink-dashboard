import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { OverviewInventory } from './OverviewInventory';

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
        latency={{ current: 20, min: 10, average: 15, max: 20 }}
        packetLoss={{ current: 1, min: 0, average: 0.5, max: 1 }}
        gep={null}
        pois={[]}
        cadence={1}
        now={new Date('2026-09-02T12:00:00Z')}
      />
    );

    expect(html.match(/data-clock=/g) ?? []).toHaveLength(4);
    expect(html).toContain('Current position map');
    expect(html).toContain('Top applicable POIs');
    expect(html).toContain('5-minute min / avg / max');
    expect(html).toContain('Download');
    expect(html).toContain('Upload');
    expect(html).toContain('Ground entry point');
    expect(html).toContain('Obstruction');
    expect(html).toContain('Packet loss');
    expect(html).toContain('Selected interval');
    expect(html).not.toContain('Grafana');
  });
});
