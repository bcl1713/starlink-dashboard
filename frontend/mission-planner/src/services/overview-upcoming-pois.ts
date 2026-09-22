import apiClient from './api-client';

export type OverviewPoiKind =
  | 'departure'
  | 'arrival'
  | 'aar_start'
  | 'aar_end'
  | 'x_band_transition'
  | 'ka_coverage_exit'
  | 'ka_coverage_entry'
  | 'ka_transition';

export interface OverviewUpcomingPoi {
  poi_id: string;
  name: string;
  kind: OverviewPoiKind;
  latitude: number;
  longitude: number;
  expected_arrival_time: string | null;
  eta_seconds: number | null;
  estimated_arrival_time: string | null;
  eta_type: 'anticipated' | 'estimated' | null;
  upcoming: boolean;
  map_retained: boolean;
}

export interface OverviewUpcomingPoisResponse {
  state:
    | 'available'
    | 'no_active_route'
    | 'no_generated_pois'
    | 'no_upcoming_pois'
    | 'unavailable';
  calculated_at: string;
  pois: OverviewUpcomingPoi[];
}

export const overviewUpcomingPoisApi = {
  async get(): Promise<OverviewUpcomingPoisResponse> {
    const response = await apiClient.get<OverviewUpcomingPoisResponse>(
      '/api/overview/upcoming-pois'
    );
    return response.data;
  },
};
