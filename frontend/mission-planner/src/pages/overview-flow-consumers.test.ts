import { describe, expect, it } from 'vitest';
import {
  activeLinkFlowEmitters,
  routeFlowEmitters,
} from './overview-flow-consumers';

describe('overview flow-line consumers', () => {
  it('uses a fixed forward-only route direction without telemetry knowledge', () => {
    expect(routeFlowEmitters()).toMatchObject({
      forward: { enabled: true, rate: expect.any(Number) },
      reverse: { enabled: false },
    });
  });

  it('maps upload forward and download reverse on aircraft-to-satellite links', () => {
    const emitters = activeLinkFlowEmitters({
      throughput_down_mbps: 100,
      throughput_up_mbps: 10,
      latency_ms: 50,
      packet_loss_percent: 10,
    });

    expect(emitters.forward).toMatchObject({
      enabled: true,
      color: '#fbbf24',
    });
    expect(emitters.reverse).toMatchObject({
      enabled: true,
      color: '#67e8f9',
    });
    expect(emitters.reverse.rate).toBeGreaterThan(emitters.forward.rate);
    expect(emitters.forward.failure?.probability).toBeCloseTo(0.1);
    expect(emitters.reverse.failure?.probability).toBeCloseTo(0.1);
    expect(emitters.forward.failure?.color).toBe('#ff304f');
    expect(emitters.reverse.failure?.color).toBe('#ff304f');
  });

  it('makes high-latency packets dimmer and smaller without changing speed', () => {
    const lowLatency = activeLinkFlowEmitters({
      throughput_down_mbps: 20,
      throughput_up_mbps: 20,
      latency_ms: 20,
    });
    const highLatency = activeLinkFlowEmitters({
      throughput_down_mbps: 20,
      throughput_up_mbps: 20,
      latency_ms: 400,
    });

    expect(highLatency.forward.speed).toBe(lowLatency.forward.speed);
    expect(highLatency.reverse.speed).toBe(lowLatency.reverse.speed);
    expect(highLatency.forward.brightness).toBeLessThan(
      lowLatency.forward.brightness
    );
    expect(highLatency.forward.size).toBeLessThan(lowLatency.forward.size);
  });

  it('does not emit packets for zero throughput', () => {
    const emitters = activeLinkFlowEmitters({
      throughput_down_mbps: 0,
      throughput_up_mbps: 0,
      latency_ms: 40,
    });

    expect(emitters.forward).toMatchObject({ enabled: false, rate: 0 });
    expect(emitters.reverse).toMatchObject({ enabled: false, rate: 0 });
  });

  it('disables data-driven link emitters when telemetry is absent', () => {
    expect(activeLinkFlowEmitters(undefined)).toMatchObject({
      forward: { enabled: false },
      reverse: { enabled: false },
    });
  });
});
