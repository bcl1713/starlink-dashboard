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

export interface POIListResponse {
  pois: POI[];
  total: number;
  route_id?: string | null;
  mission_id?: string | null;
}

export const poisService = {
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
      console.warn(`Failed to load POIs for mission ${missionId}:`, error);
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
      console.warn(`Failed to load POIs for route ${routeId}:`, error);
      return [];
    }
  },

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
      console.warn('Failed to load POIs:', error);
      return [];
    }
  },
};
