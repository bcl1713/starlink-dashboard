import type { FlowEmitterConfig } from './overview-animated-flow-line-rendering';

export interface LinkTelemetry {
  throughput_down_mbps?: number;
  throughput_up_mbps?: number;
  latency_ms?: number;
  packet_loss_percent?: number;
}

export type FlowEmitters = {
  forward: FlowEmitterConfig;
  reverse: FlowEmitterConfig;
};

const DISABLED: FlowEmitterConfig = {
  enabled: false,
  rate: 0,
  speed: 0,
  color: '#ffffff',
  size: 1,
  brightness: 0,
  maxParticles: 0,
};

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function lerp(start: number, end: number, amount: number): number {
  return start + (end - start) * amount;
}

export function routeFlowEmitters(): FlowEmitters {
  return {
    // One emitter for the whole route. Speed is scene units per second, so the
    // apparent travel velocity stays consistent regardless of route length.
    forward: {
      enabled: true,
      rate: 1,
      speed: 0.1,
      color: '#ffb000',
      size: 15,
      brightness: 1.35,
      maxParticles: 1,
      maxWorldSize: 0.05,
    },
    reverse: DISABLED,
  };
}

function throughputToRate(
  mbps: number | undefined,
  maxMbps: number,
  maxRate: number
): number {
  if (mbps === undefined || !Number.isFinite(mbps) || mbps <= 0) {
    return 0;
  }

  const normalized = clamp(Math.log1p(mbps) / Math.log1p(maxMbps), 0, 1);
  return maxRate * normalized;
}

function pingToBrightness(ms: number): number {
  const normalized = clamp((ms - 20) / 280, 0, 1);
  return lerp(3.4, 0.22, Math.pow(normalized, 0.55));
}

function pingToSize(ms: number): number {
  const normalized = clamp((ms - 20) / 280, 0, 1);
  return lerp(9.5, 4.8, Math.pow(normalized, 0.7));
}

export function measuredTrafficFlowEmitters(
  telemetry: LinkTelemetry | undefined
): FlowEmitters {
  if (!telemetry) {
    return { forward: DISABLED, reverse: DISABLED };
  }

  const downlinkRate = throughputToRate(telemetry.throughput_down_mbps, 500, 5);
  const uplinkRate = throughputToRate(telemetry.throughput_up_mbps, 500, 5);
  const latency =
    telemetry.latency_ms !== undefined &&
    Number.isFinite(telemetry.latency_ms) &&
    telemetry.latency_ms >= 0
      ? telemetry.latency_ms
      : undefined;
  const loss = telemetry.packet_loss_percent;
  const packetLoss =
    loss !== undefined && Number.isFinite(loss) && loss >= 0 && loss <= 100
      ? loss / 100
      : 0;
  const size = latency === undefined ? 9.5 : pingToSize(latency);
  const brightness = latency === undefined ? 3.4 : pingToBrightness(latency);
  const failure =
    packetLoss > 0
      ? {
          probability: packetLoss,
          color: '#ff304f',
          duration: 0.42,
          minProgress: 0.15,
          maxProgress: 0.85,
        }
      : undefined;

  return {
    // Arc points are aircraft -> PoP, so forward represents upload.
    // Scene speed and bounded activity are independent of path length.
    forward: {
      enabled: uplinkRate > 0,
      rate: uplinkRate,
      speed: 0.5,
      color: '#fbbf24',
      size,
      brightness,
      maxParticles: 100,
      maxWorldSize: 0.07,
      failure,
    },
    // Reverse travels PoP -> aircraft and represents download.
    reverse: {
      enabled: downlinkRate > 0,
      rate: downlinkRate,
      speed: 0.5,
      color: '#67e8f9',
      size,
      brightness,
      maxParticles: 100,
      maxWorldSize: 0.07,
      failure,
    },
  };
}

/** Steady illustrative rendering only; these values are never observations. */
export function xBandFlowEmitters(active: boolean): FlowEmitters {
  if (!active) return { forward: DISABLED, reverse: DISABLED };
  const preset = measuredTrafficFlowEmitters({
    throughput_up_mbps: 4,
    throughput_down_mbps: 4,
    latency_ms: 500,
  });
  return {
    forward: {
      ...preset.forward,
      brightness: Math.max(1.35, preset.forward.brightness),
    },
    reverse: {
      ...preset.reverse,
      brightness: Math.max(1.35, preset.reverse.brightness),
    },
  };
}
