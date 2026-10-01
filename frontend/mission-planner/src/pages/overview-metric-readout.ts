import type { StatusResponse } from '../services/status';
import type { OverviewMetricGraphDescriptor } from './overview-metric-history';

export interface MetricReadout {
  value: number;
  observedAtMs: number;
  ageMs: number;
  state: 'fresh' | 'stale';
}

export type NetworkState = 'fresh' | 'partial' | 'stale' | 'unavailable';

/** Project only verified source observations; history timestamps are not provenance. */
export function statusMetricReadout(
  status: StatusResponse | undefined,
  descriptor: OverviewMetricGraphDescriptor,
  nowMs: number,
  requestFailed: boolean
): MetricReadout | null {
  if (!status || typeof status.timestamp !== 'string') return null;
  const observedAtMs = Date.parse(status.timestamp);
  const ageMs = nowMs - observedAtMs;
  if (!Number.isFinite(observedAtMs) || !Number.isFinite(ageMs) || ageMs < 0) {
    return null;
  }

  let field: keyof NonNullable<StatusResponse['metric_availability']>;
  let value: number | null | undefined;
  switch (descriptor.id) {
    case 'latency':
      field = 'latency_ms';
      value = status.network?.latency_ms;
      break;
    case 'downlink':
      field = 'throughput_down_mbps';
      value = status.network?.throughput_down_mbps;
      break;
    case 'uplink':
      field = 'throughput_up_mbps';
      value = status.network?.throughput_up_mbps;
      break;
    case 'packet-loss':
      field = 'packet_loss_percent';
      value = status.network?.packet_loss_percent;
      break;
    case 'obstruction':
      field = 'obstruction_percent';
      value = status.obstruction?.obstruction_percent;
      break;
    default:
      return null;
  }
  if (
    status.metric_availability?.[field] !== true ||
    typeof value !== 'number' ||
    !Number.isFinite(value)
  ) {
    return null;
  }
  return {
    value,
    observedAtMs,
    ageMs,
    state: requestFailed || ageMs >= 5_000 ? 'stale' : 'fresh',
  };
}

/** Summarize the five projected metrics without hiding gaps or last-good data. */
export function networkStatusState(
  readouts: (MetricReadout | null)[]
): NetworkState {
  if (readouts.every((readout) => readout === null)) return 'unavailable';
  if (readouts.every((readout) => readout?.state === 'fresh')) return 'fresh';
  if (readouts.every((readout) => readout?.state === 'stale')) return 'stale';
  return 'partial';
}
