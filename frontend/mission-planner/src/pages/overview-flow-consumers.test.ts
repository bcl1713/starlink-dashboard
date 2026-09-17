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

  it('maps consumer telemetry into both link directions without leaking it into the primitive', () => {
    const emitters = activeLinkFlowEmitters({
      throughput_down_mbps: 100,
      throughput_up_mbps: 10,
      latency_ms: 50,
      packet_loss_percent: 10,
    });

    expect(emitters.forward.enabled).toBe(true);
    expect(emitters.reverse.enabled).toBe(true);
    expect(emitters.forward.rate).toBeGreaterThan(emitters.reverse.rate);
    expect(emitters.forward.failure?.probability).toBeCloseTo(0.1);
    expect(emitters.reverse.failure?.probability).toBeCloseTo(0.1);
    expect(emitters.forward.failure?.color).toBe('#ff3b30');
    expect(emitters.reverse.failure?.color).toBe('#ff3b30');
  });

  it('maps latency to visible brightness and modest size without changing travel speed', () => {
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
    expect(highLatency.forward.brightness).toBeGreaterThan(
      lowLatency.forward.brightness
    );
    expect(highLatency.forward.size).toBeGreaterThan(lowLatency.forward.size);
    expect(highLatency.forward.size - lowLatency.forward.size).toBeLessThanOrEqual(
      3
    );
  });

  it('disables data-driven link emitters when telemetry is absent', () => {
    expect(activeLinkFlowEmitters(undefined)).toMatchObject({
      forward: { enabled: false },
      reverse: { enabled: false },
    });
  });
});
