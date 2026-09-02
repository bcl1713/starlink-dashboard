import type { MonitoringHistory, StatusData } from '../../services/monitoring';
import { appendSample, type NumericSample } from './history';

type Metric = MonitoringHistory['series'][number]['metric'];
export type OverviewHistoryStore = Record<Metric, NumericSample[]>;

export const createOverviewHistoryStore = (): OverviewHistoryStore => ({
  latitude_degrees: [],
  longitude_degrees: [],
  latency_ms: [],
  throughput_down_mbps: [],
  throughput_up_mbps: [],
  packet_loss_percent: [],
});

export function appendLiveStatus(
  current: OverviewHistoryStore,
  sample: StatusData,
  instant: number
): OverviewHistoryStore {
  const timestamp = sample.observed_at;
  return {
    latitude_degrees: appendSample(
      current.latitude_degrees,
      { timestamp, value: sample.position.latitude },
      instant
    ),
    longitude_degrees: appendSample(
      current.longitude_degrees,
      { timestamp, value: sample.position.longitude },
      instant
    ),
    latency_ms: appendSample(
      current.latency_ms,
      { timestamp, value: sample.network.latency_ms },
      instant
    ),
    throughput_down_mbps: appendSample(
      current.throughput_down_mbps,
      { timestamp, value: sample.network.throughput_down_mbps },
      instant
    ),
    throughput_up_mbps: appendSample(
      current.throughput_up_mbps,
      { timestamp, value: sample.network.throughput_up_mbps },
      instant
    ),
    packet_loss_percent: appendSample(
      current.packet_loss_percent,
      { timestamp, value: sample.network.packet_loss_percent },
      instant
    ),
  };
}
