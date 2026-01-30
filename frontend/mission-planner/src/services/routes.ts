import { apiClient } from './api-client';

export interface Route {
  id: string;
  name: string;
  description?: string;
  point_count?: number;
  is_active?: boolean;
  imported_at?: string;
  has_timing_data?: boolean;
  flight_phase?: string;
  eta_mode?: string;
}

export interface RouteDetail extends Route {
  points?: Array<{ latitude: number; longitude: number }>;
  waypoints?: Waypoint[];
  timing_profile?: TimingProfile;
  statistics?: {
    distance_meters: number;
    distance_km: number;
    bounds: {
      min_lat: number;
      max_lat: number;
      min_lon: number;
      max_lon: number;
    };
  };
  poi_count?: number;
}

export interface Waypoint {
  name?: string;
  latitude: number;
  longitude: number;
  altitude?: number;
  description?: string;
}

export interface TimingProfile {
  [key: string]: string | number;
}

interface RouteDetailResponse {
  points?: Array<{ latitude: number; longitude: number }>;
  waypoints?: Waypoint[];
  timing_profile?: TimingProfile;
  flight_phase?: string;
}

interface RouteListResponse {
  routes: Route[];
  total: number;
}

export const routesApi = {
  async list(): Promise<Route[]> {
    const response = await apiClient.get<RouteListResponse>('/api/routes');
    return response.data.routes || [];
  },

  async get(routeId: string): Promise<RouteDetail> {
    const response = await apiClient.get<RouteDetailResponse>(
      `/api/routes/${routeId}`
    );
    return response.data as RouteDetail;
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

  async delete(routeId: string): Promise<void> {
    await apiClient.delete(`/api/routes/${routeId}`);
  },

  async activate(routeId: string): Promise<Route> {
    const response = await apiClient.post<Route>(
      `/api/routes/${routeId}/activate`
    );
    return response.data;
  },

  async deactivate(routeId: string): Promise<Route> {
    const response = await apiClient.post<Route>(
      `/api/routes/${routeId}/deactivate`
    );
    return response.data;
  },

  async download(routeId: string): Promise<Blob> {
    const response = await apiClient.get<Blob>(
      `/api/routes/${routeId}/download`,
      {
        responseType: 'blob',
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
