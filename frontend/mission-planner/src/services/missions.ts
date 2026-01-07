import { apiClient } from './api-client';
import type {
  Mission,
  CreateMissionRequest,
  UpdateMissionRequest,
  MissionLeg,
  UpdateLegRouteResponse,
  UpdateLegResponse,
} from '../types/mission';

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

  update: async (id: string, updates: UpdateMissionRequest) => {
    const response = await apiClient.patch<Mission>(
      `/api/v2/missions/${id}`,
      updates
    );
    return response.data;
  },

  delete: async (id: string) => {
    const response = await apiClient.delete(`/api/v2/missions/${id}`);
    return response.data;
  },

  addLeg: async (missionId: string, leg: Partial<MissionLeg>) => {
    const response = await apiClient.post<MissionLeg>(
      `/api/v2/missions/${missionId}/legs`,
      leg
    );
    return response.data;
  },

  updateLeg: async (
    missionId: string,
    legId: string,
    leg: MissionLeg
  ): Promise<UpdateLegResponse> => {
    const response = await apiClient.put<UpdateLegResponse>(
      `/api/v2/missions/${missionId}/legs/${legId}`,
      leg
    );
    return response.data;
  },

  deleteLeg: async (missionId: string, legId: string) => {
    const response = await apiClient.delete(
      `/api/v2/missions/${missionId}/legs/${legId}`
    );
    return response.data;
  },

  activateLeg: async (missionId: string, legId: string): Promise<void> => {
    await apiClient.post(
      `/api/v2/missions/${missionId}/legs/${legId}/activate`
    );
  },

  deactivateAllLegs: async (missionId: string): Promise<void> => {
    await apiClient.post(`/api/v2/missions/${missionId}/legs/deactivate`);
  },

  updateLegRoute: async (
    missionId: string,
    legId: string,
    kmlFile: File
  ): Promise<UpdateLegRouteResponse> => {
    const formData = new FormData();
    formData.append('file', kmlFile);

    const response = await apiClient.put<UpdateLegRouteResponse>(
      `/api/v2/missions/${missionId}/legs/${legId}/route`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },
};
