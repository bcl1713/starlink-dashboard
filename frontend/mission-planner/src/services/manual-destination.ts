import apiClient from './api-client';

export interface ManualDestination {
  name: string;
  latitude: number;
  longitude: number;
  airport_code: string | null;
}
export interface ManualDestinationSettings {
  destination: ManualDestination | null;
}
export interface Airport {
  ident: string;
  name: string;
  latitude: number;
  longitude: number;
  icao_code: string | null;
  iata_code: string | null;
  gps_code: string | null;
  local_code: string | null;
  municipality: string | null;
  country: string;
}
export const manualDestinationApi = {
  async get(): Promise<ManualDestinationSettings> {
    return (
      await apiClient.get<ManualDestinationSettings>(
        '/api/overview/manual-destination'
      )
    ).data;
  },
  async save(
    destination: ManualDestination | null
  ): Promise<ManualDestinationSettings> {
    return (
      await apiClient.put<ManualDestinationSettings>(
        '/api/overview/manual-destination',
        { destination }
      )
    ).data;
  },
  async search(q: string): Promise<Airport[]> {
    return (
      await apiClient.get<{ airports: Airport[] }>('/api/overview/airports', {
        params: { q },
      })
    ).data.airports;
  },
};
