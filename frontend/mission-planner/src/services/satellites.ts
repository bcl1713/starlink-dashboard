import { apiClient } from './api-client';

/**
 * Satellite metadata from the backend catalog.
 */
export interface Satellite {
  satellite_id: string;
  transport: string;
  longitude?: number;
  slot?: string;
  color: string;
}

/**
 * API service for accessing satellite catalog data.
 *
 * Provides methods to fetch available satellites from the backend
 * satellite catalog, enabling dynamic satellite selection in the UI.
 */
export const satellitesApi = {
  /**
   * List all available satellites from the catalog.
   *
   * Fetches the complete list of X-Band satellites currently available
   * for mission planning.
   *
   * @returns Promise resolving to array of satellite objects
   * @throws Error if the API request fails
   *
   * @example
   * const satellites = await satellitesApi.list();
   * console.log(satellites); // [{ satellite_id: 'X-1', transport: 'X', ... }]
   */
  async list(): Promise<Satellite[]> {
    const response = await apiClient.get<Satellite[]>('/api/satellites');
    return response.data;
  },
};
