import apiClient from './api-client';

/**
 * The active-link endpoint supplies current selection and warning semantics.
 * Satellite coordinates remain authoritative only from /api/satellites.
 */
export interface ActiveXLinkSelectionResponse {
  satellite_id: string | null;
  state?: 'normal' | 'warning' | null;
}
export const activeXLinkApi = {
  async get(): Promise<ActiveXLinkSelectionResponse> {
    const response =
      await apiClient.get<ActiveXLinkSelectionResponse>('/api/active-x-link');
    return response.data;
  },
};
