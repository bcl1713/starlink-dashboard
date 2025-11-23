import { apiClient } from './api-client';
import type { ImportResult } from '../types/export';

export const exportImportApi = {
  exportMission: async (missionId: string): Promise<Blob> => {
    const response = await apiClient.post(
      `/api/v2/missions/${missionId}/export`,
      {},
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  importMission: async (file: File): Promise<ImportResult> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post<ImportResult>(
      '/api/v2/missions/import',
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
