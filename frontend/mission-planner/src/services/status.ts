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
  network?: {
    latency_ms?: number;
    throughput_down_mbps?: number;
    throughput_up_mbps?: number;
    packet_loss_percent?: number;
  };
  environmental?: {
    signal_quality_percent?: number;
  };
}

export const statusApi = {
  async get(): Promise<StatusResponse> {
    const response = await apiClient.get<StatusResponse>('/api/status');
    return response.data;
  },
};
