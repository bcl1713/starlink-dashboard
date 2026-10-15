import apiClient from './api-client';

export interface StatusResponse {
  timestamp: string;
  position?: {
    latitude: number;
    longitude: number;
    altitude?: number;
    speed?: number;
    heading?: number;
  };
  /** Source availability for the shared telemetry sample; absent flags fail closed. */
  metric_availability?: Partial<
    Record<
      | 'latency_ms'
      | 'throughput_down_mbps'
      | 'throughput_up_mbps'
      | 'packet_loss_percent'
      | 'obstruction_percent',
      boolean
    >
  >;
  network?: {
    latency_ms?: number | null;
    throughput_down_mbps?: number | null;
    throughput_up_mbps?: number | null;
    packet_loss_percent?: number | null;
  };
  obstruction?: {
    obstruction_percent?: number | null;
  };
  environmental?: {
    signal_quality_percent?: number;
  };
  ground_entry_point?: {
    latitude: number;
    longitude: number;
  } | null;
}

export const statusApi = {
  async get(): Promise<StatusResponse> {
    const response = await apiClient.get<StatusResponse>('/api/status');
    return response.data;
  },
};
