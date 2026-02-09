import { apiClient } from './api-client';
import type { GPSConfig, GPSConfigUpdate, GPSError } from '../types/gps';

export const gpsService = {
  /**
   * Get current GPS configuration and status from Starlink dish
   */
  async getGPSConfig(): Promise<GPSConfig> {
    const response = await apiClient.get<GPSConfig>('/api/v2/gps/config');
    return response.data;
  },

  /**
   * Update GPS configuration on Starlink dish
   */
  async setGPSConfig(update: GPSConfigUpdate): Promise<GPSConfig> {
    const response = await apiClient.post<GPSConfig>(
      '/api/v2/gps/config',
      update
    );
    return response.data;
  },

  /**
   * Parse API error into typed GPS error
   */
  parseError(error: unknown): GPSError {
    if (error instanceof Error) {
      const cause = (
        error as Error & { cause?: { response?: { status?: number } } }
      ).cause;
      const status = cause?.response?.status;

      if (status === 403) {
        return {
          type: 'permission_denied',
          message: 'GPS configuration is not permitted on this dish',
        };
      }

      if (status === 503) {
        return {
          type: 'unavailable',
          message: 'Starlink dish is not available',
        };
      }

      return {
        type: 'unknown',
        message: error.message,
      };
    }

    return {
      type: 'unknown',
      message: 'An unknown error occurred',
    };
  },
};
