import { apiClient } from './api-client';

// Backend satellite response from /api/satellites
export interface SatelliteResponse {
  satellite_id: string;
  transport: string;
  longitude: number | null;
  slot: string | null;
  color: string;
}

// Request model for creating a satellite
export interface SatelliteCreateRequest {
  satellite_id: string;
  transport: string;
  longitude: number;
  slot?: string | null;
  color?: string;
}

// Request model for updating a satellite
export interface SatelliteUpdateRequest {
  satellite_id?: string;
  transport?: string;
  longitude?: number;
  slot?: string | null;
  color?: string;
}

export const satelliteService = {
  async getAll(): Promise<SatelliteResponse[]> {
    const response = await apiClient.get('/api/satellites');
    return response.data;
  },

  async create(satellite: SatelliteCreateRequest): Promise<SatelliteResponse> {
    const response = await apiClient.post('/api/satellites', satellite);
    return response.data;
  },

  async update(
    satelliteId: string,
    updates: SatelliteUpdateRequest
  ): Promise<SatelliteResponse> {
    const response = await apiClient.put(
      `/api/satellites/${satelliteId}`,
      updates
    );
    return response.data;
  },

  async delete(satelliteId: string): Promise<void> {
    await apiClient.delete(`/api/satellites/${satelliteId}`);
  },
};
