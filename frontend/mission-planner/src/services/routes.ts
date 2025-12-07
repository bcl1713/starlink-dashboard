import { apiClient } from './api-client';

export interface Route {
  id: string;
  name: string;
  description?: string;
  waypoint_count?: number;
}

export interface Waypoint {
  name?: string;
  latitude: number;
  longitude: number;
  altitude?: number;
  description?: string;
}

interface RouteDetailResponse {
  points?: Array<{ latitude: number; longitude: number }>;
  waypoints?: Waypoint[];
}

export const routesApi = {
  async list(): Promise<Route[]> {
    const response = await apiClient.get<{ routes: Route[]; total: number }>(
      '/api/routes'
    );
    return response.data.routes || [];
  },

  async upload(file: File): Promise<Route> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<Route>(
      '/api/routes/upload?import_pois=true',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  async getCoordinates(routeId: string): Promise<[number, number][]> {
    const response = await apiClient.get<RouteDetailResponse>(
      `/api/routes/${routeId}`
    );
    // Extract coordinates from points (cleaned/calculated route)
    // NOT waypoints (those are named placemarks)
    if (response.data.points && Array.isArray(response.data.points)) {
      return response.data.points.map((point) => [
        point.latitude,
        point.longitude,
      ]);
    }
    return [];
  },

  async getWaypoints(routeId: string): Promise<Waypoint[]> {
    const response = await apiClient.get<RouteDetailResponse>(
      `/api/routes/${routeId}`
    );
    // Extract full waypoint objects from the route detail response
    if (response.data.waypoints && Array.isArray(response.data.waypoints)) {
      return response.data.waypoints.filter(
        (waypoint) => waypoint.name !== undefined && waypoint.name !== ''
      );
    }
    return [];
  },

  async getWaypointNames(routeId: string): Promise<string[]> {
    const waypoints = await this.getWaypoints(routeId);
    return waypoints.map((wp) => wp.name || '').filter((name) => name !== '');
  },
};
