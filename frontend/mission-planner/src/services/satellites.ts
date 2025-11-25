import { apiClient } from './api-client';
import type { Satellite } from '../types/satellite';

export const satelliteService = {
  async getAll(): Promise<Satellite[]> {
    const response = await apiClient.get('/api/satellites');
    return response.data;
  },

  async create(satellite: Omit<Satellite, 'id'>): Promise<Satellite> {
    const response = await apiClient.post('/api/satellites', satellite);
    return response.data;
  },

  async update(id: string, satellite: Partial<Satellite>): Promise<Satellite> {
    const response = await apiClient.put(`/api/satellites/${id}`, satellite);
    return response.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/satellites/${id}`);
  },
};
