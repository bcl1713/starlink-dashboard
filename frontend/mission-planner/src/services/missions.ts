import { apiClient } from './api-client';
import type { Mission, CreateMissionRequest } from '../types/mission';

export const missionsApi = {
  list: async () => {
    const response = await apiClient.get<Mission[]>('/api/v2/missions');
    return response.data;
  },

  get: async (id: string) => {
    const response = await apiClient.get<Mission>(`/api/v2/missions/${id}`);
    return response.data;
  },

  create: async (mission: CreateMissionRequest) => {
    const response = await apiClient.post<Mission>('/api/v2/missions', mission);
    return response.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/api/v2/missions/${id}`);
  },
};
