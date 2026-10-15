import apiClient from './api-client';

/**
 * The active-link endpoint supplies current selection and warning semantics.
 * Satellite coordinates remain authoritative only from /api/satellites.
 */
export interface ActiveXLinkSelectionResponse {
  satellite_id: string | null;
  state?: 'normal' | 'warning' | null;
  selection_source?: 'mission' | 'manual' | 'none';
  manual_satellite_id?: string | null;
  manual_selection_invalid?: boolean;
  manual_selection_unavailable?: boolean;
}
export const activeXLinkApi = {
  async get(signal?: AbortSignal): Promise<ActiveXLinkSelectionResponse> {
    const response = await apiClient.get<ActiveXLinkSelectionResponse>(
      '/api/active-x-link',
      { signal }
    );
    return response.data;
  },
  async update(
    satelliteId: string | null
  ): Promise<ActiveXLinkSelectionResponse> {
    const response = await apiClient.put<ActiveXLinkSelectionResponse>(
      '/api/active-x-link/selection',
      { satellite_id: satelliteId }
    );
    return response.data;
  },
};
