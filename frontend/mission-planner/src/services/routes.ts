import { apiClient } from './api-client';

export interface Route {
  id: string;
  name: string;
  description?: string;
  waypoint_count?: number;
}

export const routesApi = {
  async list(): Promise<Route[]> {
    const response = await apiClient.get<Route[]>('/api/routes');
    return response.data;
  },

  async upload(file: File): Promise<Route> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<Route>('/api/routes/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};
