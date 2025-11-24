import { apiClient } from './api-client';

export interface Route {
  id: string;
  name: string;
  description?: string;
  waypoint_count?: number;
}

export const routesApi = {
  async list(): Promise<Route[]> {
    const response = await apiClient.get<{ routes: Route[]; total: number }>('/api/routes');
    return response.data.routes || [];
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

  async getCoordinates(routeId: string): Promise<[number, number][]> {
    const response = await apiClient.get<any>(`/api/routes/${routeId}`);
    // Extract coordinates from points (cleaned/calculated route)
    // NOT waypoints (those are named placemarks)
    if (response.data.points && Array.isArray(response.data.points)) {
      return response.data.points.map((point: any) => [point.latitude, point.longitude]);
    }
    return [];
  },
};
