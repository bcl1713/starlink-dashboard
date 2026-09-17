import type { FlowEmitterConfig } from './overview-animated-flow-line-rendering';

export interface LinkTelemetry {
  throughput_down_mbps?: number;
  throughput_up_mbps?: number;
  latency_ms?: number;
  packet_loss_percent?: number;
}

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

export function routeFlowEmitters(): {
  forward: FlowEmitterConfig;
  reverse: FlowEmitterConfig;
} {
  return {
    forward: {
      enabled: true,
      rate: 0.8,
      speed: 0.18,
      color: '#ffb000',
      size: 6,
      brightness: 1.2,
      maxParticles: 8,
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

export function activeLinkFlowEmitters(telemetry: LinkTelemetry | undefined): {
  forward: FlowEmitterConfig;
  reverse: FlowEmitterConfig;
} {
  if (!telemetry) {
    return { forward: DISABLED, reverse: DISABLED };
  }

  const downlinkRate = throughputToRate(
    telemetry.throughput_down_mbps,
    500,
    3.2
  );
  const uplinkRate = throughputToRate(
    telemetry.throughput_up_mbps,
    100,
    1.8
  );
  const latency =
    telemetry.latency_ms !== undefined && Number.isFinite(telemetry.latency_ms)
      ? Math.max(0, telemetry.latency_ms)
      : 100;
  const packetLoss = clamp(
    (telemetry.packet_loss_percent ?? 0) / 100,
    0,
    1
  );
  const size = pingToSize(latency);
  const brightness = pingToBrightness(latency);
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
    // Link points are aircraft -> satellite, so forward represents upload.
    forward: {
      enabled: uplinkRate > 0,
      rate: uplinkRate,
      speed: 0.22,
      color: '#fbbf24',
      size,
      brightness,
      maxParticles: 16,
      maxWorldSize: 0.07,
      failure,
    },
    // Reverse travels satellite -> aircraft and represents download.
    reverse: {
      enabled: downlinkRate > 0,
      rate: downlinkRate,
      speed: 0.22,
      color: '#67e8f9',
      size,
      brightness,
      maxParticles: 24,
      maxWorldSize: 0.07,
      failure,
    },
  };
}
