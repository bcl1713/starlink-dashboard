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

export function routeFlowEmitters(): {
  forward: FlowEmitterConfig;
  reverse: FlowEmitterConfig;
} {
  return {
    forward: {
      enabled: true,
      rate: 1.5,
      speed: 0.16,
      color: '#ffb000',
      size: 6,
      brightness: 1.1,
      maxParticles: 8,
    },
    reverse: DISABLED,
  };
}

function throughputRate(mbps: number): number {
  return Math.min(8, Math.max(0.25, Math.log2(mbps + 1) / 1.5));
}

export function activeLinkFlowEmitters(telemetry: LinkTelemetry | undefined): {
  forward: FlowEmitterConfig;
  reverse: FlowEmitterConfig;
} {
  const downlink = telemetry?.throughput_down_mbps;
  const uplink = telemetry?.throughput_up_mbps;
  if (
    !Number.isFinite(downlink) ||
    !Number.isFinite(uplink) ||
    downlink === undefined ||
    uplink === undefined
  ) {
    return { forward: DISABLED, reverse: DISABLED };
  }

  const packetLoss = Math.min(
    1,
    Math.max(0, (telemetry?.packet_loss_percent ?? 0) / 100)
  );
  const latency = Math.max(0, telemetry?.latency_ms ?? 0);
  const speed = Math.max(0.08, 0.28 - Math.min(latency, 500) / 4_000);
  const failure = packetLoss > 0 ? { probability: packetLoss } : undefined;
  return {
    forward: {
      enabled: true,
      rate: throughputRate(downlink),
      speed,
      color: '#72b7ff',
      size: 7,
      brightness: 1.1,
      maxParticles: 12,
      failure,
    },
    reverse: {
      enabled: true,
      rate: throughputRate(uplink),
      speed,
      color: '#c084fc',
      size: 6,
      brightness: 0.9,
      maxParticles: 8,
      failure,
    },
  };
}
