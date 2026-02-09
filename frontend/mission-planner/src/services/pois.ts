import { apiClient } from './api-client';

export interface POI {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  icon: string;
  category: string | null;
  description?: string;
  route_id?: string | null;
  mission_id?: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface POICreate {
  name: string;
  latitude: number;
  longitude: number;
  icon: string;
  category?: string | null;
  description?: string;
  route_id?: string | null;
  mission_id?: string | null;
}

export interface POIUpdate {
  name?: string;
  latitude?: number;
  longitude?: number;
  icon?: string;
  category?: string | null;
  description?: string;
  route_id?: string | null;
  mission_id?: string | null;
}

export interface POIWithETA extends POI {
  poi_id?: string;
  eta?: string;
  eta_seconds?: number;
  eta_type?: 'anticipated' | 'estimated';
  bearing?: number;
  bearing_degrees?: number;
  course_status?: 'on_course' | 'slightly_off' | 'off_track' | 'behind' | null;
  distance_meters?: number;
  is_on_active_route?: boolean;
  projected_latitude?: number | null;
  projected_longitude?: number | null;
  projected_waypoint_index?: number | null;
  projected_route_progress?: number | null;
  route_aware_status?:
    | 'ahead_on_route'
    | 'already_passed'
    | 'not_on_route'
    | 'pre_departure'
    | null;
  flight_phase?: string | null;
}

export interface POIListResponse {
  pois: POI[];
  total: number;
  route_id?: string | null;
  mission_id?: string | null;
}

export const poisService = {
  /**
   * Get all POIs
   */
  async getAllPOIs(activeOnly: boolean = true): Promise<POI[]> {
    try {
      const response = await apiClient.get<POIListResponse>('/api/pois', {
        params: {
          active_only: activeOnly,
        },
      });
      return response.data.pois;
    } catch (error) {
      console.error('Failed to load POIs:', error);
      return [];
    }
  },

  /**
   * Get POIs for a specific mission
   */
  async getPOIsByMission(
    missionId: string,
    activeOnly: boolean = true
  ): Promise<POI[]> {
    try {
      const response = await apiClient.get<POIListResponse>('/api/pois', {
        params: {
          mission_id: missionId,
          active_only: activeOnly,
        },
      });
      return response.data.pois;
    } catch (error) {
      console.error(`Failed to load POIs for mission ${missionId}:`, error);
      return [];
    }
  },

  /**
   * Get POIs for a specific route
   */
  async getPOIsByRoute(
    routeId: string,
    activeOnly: boolean = true
  ): Promise<POI[]> {
    try {
      const response = await apiClient.get<POIListResponse>('/api/pois', {
        params: {
          route_id: routeId,
          active_only: activeOnly,
        },
      });
      return response.data.pois;
    } catch (error) {
      console.error(`Failed to load POIs for route ${routeId}:`, error);
      return [];
    }
  },

  /**
   * Get a single POI by ID
   */
  async getPOI(poiId: string): Promise<POI> {
    const response = await apiClient.get<POI>(`/api/pois/${poiId}`);
    return response.data;
  },

  /**
   * Create a new POI
   */
  async createPOI(poi: POICreate): Promise<POI> {
    const response = await apiClient.post<POI>('/api/pois', poi);
    return response.data;
  },

  /**
   * Update an existing POI
   */
  async updatePOI(poiId: string, updates: POIUpdate): Promise<POI> {
    const response = await apiClient.put<POI>(`/api/pois/${poiId}`, updates);
    return response.data;
  },

  /**
   * Delete a POI
   */
  async deletePOI(poiId: string): Promise<void> {
    await apiClient.delete(`/api/pois/${poiId}`);
  },

  /**
   * Get POIs with real-time ETA data
   */
  async getPOIsWithETA(activeOnly: boolean = true): Promise<POIWithETA[]> {
    const response = await apiClient.get<{
      pois: POIWithETA[];
      total: number;
    }>('/api/pois/telemetry/with_eta', {
      params: {
        active_only: activeOnly,
      },
    });
    return response.data.pois;
  },
};
