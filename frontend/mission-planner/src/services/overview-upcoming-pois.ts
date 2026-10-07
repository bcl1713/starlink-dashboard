import apiClient from './api-client';
import type { MissionTimeContext } from './simulation-run';

export type OverviewPoiKind =
  | 'departure'
  | 'arrival'
  | 'aar_start'
  | 'aar_end'
  | 'x_band_transition'
  | 'x_band_warning_start'
  | 'x_band_warning_end'
  | 'ka_coverage_exit'
  | 'ka_coverage_entry'
  | 'ka_transition';

export interface OverviewUpcomingPoi {
  poi_id: string;
  name: string;
  kind: OverviewPoiKind;
  projected_route_progress: number | null;
  flight_phase: OverviewFlightPhase;
  latitude: number;
  longitude: number;
  expected_arrival_time: string | null;
  eta_seconds: number | null;
  estimated_arrival_time: string | null;
  eta_type: 'anticipated' | 'estimated' | null;
  upcoming: boolean;
  map_retained: boolean;
}

export type OverviewFlightPhase =
  | 'pre_departure'
  | 'in_flight'
  | 'post_arrival';

export interface OverviewUpcomingPoisResponse {
  mission_time?: MissionTimeContext | null;
  state:
    | 'available'
    | 'no_active_mission'
    | 'route_unavailable'
    | 'inconsistent_active_mission'
    | 'no_generated_pois'
    | 'no_upcoming_pois'
    | 'unavailable';
  calculated_at: string;
  flight_phase: OverviewFlightPhase | null;
  scheduled_departure_time: string | null;
  current_route_progress: number | null;
  position_observed_at: string | null;
  position_state: 'fresh' | 'stale' | 'unavailable';
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
