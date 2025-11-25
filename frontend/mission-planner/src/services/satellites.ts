import { apiClient } from './api-client';

// Backend satellite response from /api/satellites
export interface SatelliteResponse {
  satellite_id: string;
  transport: string;
  longitude: number | null;
  slot: string | null;
  color: string;
}

export const satelliteService = {
  async getAll(): Promise<SatelliteResponse[]> {
    const response = await apiClient.get('/api/satellites');
    return response.data;
  },
};
