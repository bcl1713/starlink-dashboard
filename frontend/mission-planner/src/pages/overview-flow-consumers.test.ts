import { describe, expect, it } from 'vitest';
import {
  measuredTrafficFlowEmitters,
  routeFlowEmitters,
  xBandFlowEmitters,
} from './overview-flow-consumers';

describe('overview flow-line consumers', () => {
  it('uses a fixed forward-only route direction without telemetry knowledge', () => {
    expect(routeFlowEmitters()).toMatchObject({
      forward: {
        enabled: true,
        rate: expect.any(Number),
        maxWorldSize: 0.05,
      },
      reverse: { enabled: false },
    });
  });

  it('maps upload forward and download reverse on aircraft-to-PoP arcs', () => {
    const emitters = measuredTrafficFlowEmitters({
      throughput_down_mbps: 100,
      throughput_up_mbps: 10,
      latency_ms: 50,
      packet_loss_percent: 10,
    });

    expect(emitters.forward).toMatchObject({
      enabled: true,
      color: '#fbbf24',
      maxWorldSize: 0.07,
    });
    expect(emitters.reverse).toMatchObject({
      enabled: true,
      color: '#67e8f9',
      maxWorldSize: 0.07,
    });
    expect(emitters.reverse.rate).toBeGreaterThan(emitters.forward.rate);
    expect(emitters.forward.failure?.probability).toBeCloseTo(0.1);
    expect(emitters.reverse.failure?.probability).toBeCloseTo(0.1);
    expect(emitters.forward.failure?.color).toBe('#ff304f');
    expect(emitters.reverse.failure?.color).toBe('#ff304f');
  });

  it('makes high-latency packets dimmer and smaller without changing speed', () => {
    const lowLatency = measuredTrafficFlowEmitters({
      throughput_down_mbps: 20,
      throughput_up_mbps: 20,
      latency_ms: 20,
    });
    const highLatency = measuredTrafficFlowEmitters({
      throughput_down_mbps: 20,
      throughput_up_mbps: 20,
      latency_ms: 400,
    });

    expect(highLatency.forward.speed).toBe(lowLatency.forward.speed);
    expect(highLatency.reverse.speed).toBe(lowLatency.reverse.speed);
    expect(highLatency.forward.brightness).toBeLessThan(
      lowLatency.forward.brightness
    );
    expect(lowLatency.forward.size).toBeCloseTo(9.5);
    expect(highLatency.forward.size).toBeCloseTo(4.8);
    expect(highLatency.forward.size).toBeLessThan(lowLatency.forward.size);
  });

  it('does not emit packets for zero throughput', () => {
    const emitters = measuredTrafficFlowEmitters({
      throughput_down_mbps: 0,
      throughput_up_mbps: 0,
      latency_ms: 40,
    });

    expect(emitters.forward).toMatchObject({ enabled: false, rate: 0 });
    expect(emitters.reverse).toMatchObject({ enabled: false, rate: 0 });
  });

  it('disables data-driven link emitters when telemetry is absent', () => {
    expect(measuredTrafficFlowEmitters(undefined)).toMatchObject({
      forward: { enabled: false },
      reverse: { enabled: false },
    });
  });

  // Catch invented RTTs, clamped invalid loss, and coupled direction gates.
  it.each([undefined, NaN, Infinity, -Infinity, -1])(
    'uses neutral appearance when latency is %s',
    (latency_ms) => {
      const flow = measuredTrafficFlowEmitters({
        throughput_up_mbps: 4,
        throughput_down_mbps: 4,
        latency_ms,
      });
      for (const emitter of [flow.forward, flow.reverse]) {
        expect(emitter).toMatchObject({
          enabled: true,
          size: 9.5,
          brightness: 3.4,
        });
      }
    }
  );

  it('accepts zero latency as a valid observation', () => {
    expect(
      measuredTrafficFlowEmitters({ throughput_up_mbps: 4, latency_ms: 0 })
        .forward
    ).toMatchObject({ enabled: true, size: 9.5, brightness: 3.4 });
  });

  it.each([undefined, NaN, Infinity, -Infinity, -1, 101])(
    'omits loss modulation when loss is %s',
    (packet_loss_percent) => {
      const flow = measuredTrafficFlowEmitters({
        throughput_up_mbps: 4,
        throughput_down_mbps: 4,
        packet_loss_percent,
      });
      expect(flow.forward.enabled).toBe(true);
      expect(flow.forward.failure).toBeUndefined();
      expect(flow.reverse.failure).toBeUndefined();
    }
  );

  it.each([0, 100])(
    'accepts boundary packet loss %s',
    (packet_loss_percent) => {
      const flow = measuredTrafficFlowEmitters({
        throughput_up_mbps: 4,
        packet_loss_percent,
      });
      if (packet_loss_percent === 0)
        expect(flow.forward.failure).toBeUndefined();
      else expect(flow.forward.failure?.probability).toBe(1);
    }
  );

  it.each([undefined, NaN, Infinity, -Infinity, -1, 0])(
    'disables only the direction with unusable throughput %s',
    (throughput) => {
      const up = measuredTrafficFlowEmitters({
        throughput_up_mbps: throughput,
        throughput_down_mbps: 4,
      });
      const down = measuredTrafficFlowEmitters({
        throughput_up_mbps: 4,
        throughput_down_mbps: throughput,
      });
      expect(up.forward).toMatchObject({ enabled: false, rate: 0 });
      expect(up.reverse.enabled).toBe(true);
      expect(down.forward.enabled).toBe(true);
      expect(down.reverse).toMatchObject({ enabled: false, rate: 0 });
    }
  );

  it('bounds logarithmic activity with fixed scene speed and per-direction caps', () => {
    const low = measuredTrafficFlowEmitters({
      throughput_up_mbps: 4,
      throughput_down_mbps: 4,
    });
    const high = measuredTrafficFlowEmitters({
      throughput_up_mbps: 500,
      throughput_down_mbps: 1_000_000,
    });
    expect(low.forward.rate).toBeGreaterThan(0);
    expect(low.forward.rate).toBeLessThan(5);
    expect(low.forward.rate).toBeGreaterThan((5 * 4) / 500);
    for (const emitter of [
      low.forward,
      low.reverse,
      high.forward,
      high.reverse,
    ]) {
      expect(emitter).toMatchObject({ speed: 0.5, maxParticles: 100 });
    }
    expect(high.forward.rate).toBe(5);
    expect(high.reverse.rate).toBe(5);
  });

  it('keeps illustrative X-band visible without measured data', () => {
    const preset = xBandFlowEmitters(true);
    expect(preset.forward.brightness).toBeGreaterThanOrEqual(1.35);
    expect(preset.reverse.rate).toBe(preset.forward.rate);
    expect(preset.forward.failure).toBeUndefined();
    for (const emitter of [preset.forward, preset.reverse]) {
      expect(emitter).toMatchObject({
        enabled: true,
        speed: 0.5,
        size: 4.8,
        brightness: 1.35,
        maxParticles: 100,
      });
      expect(emitter.rate).toBeCloseTo(1.2945, 3);
      expect(emitter.failure).toBeUndefined();
    }
    expect(xBandFlowEmitters(true)).toEqual(preset);
  });

  it('disables both illustrative directions when X-band is ineligible', () => {
    expect(xBandFlowEmitters(false)).toMatchObject({
      forward: { enabled: false, rate: 0 },
      reverse: { enabled: false, rate: 0 },
    });
  });
});
