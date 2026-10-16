/** Additive PoP wire records. Geography and lifecycle remain backend-owned. */
export interface PopCrossing {
  id: string;
  from_pop_id: string;
  to_pop_id: string;
  from_city?: string | null;
  to_city?: string | null;
  segment_index: number;
  fraction: number;
  latitude: number;
  longitude: number;
  distance_meters: number;
}
export interface PopTransition {
  crossing: PopCrossing;
  crossing_utc: string;
  window_start_utc: string;
  window_end_utc: string;
}
export interface PopForecast {
  revision: string;
  catalog_fingerprint: string;
  status: 'ready' | 'disabled' | 'unavailable' | 'indeterminate';
  reason?: string | null;
  transitions: PopTransition[];
}
export interface PopObservation {
  ip: string | null;
  entry: {
    ip: string;
    city: string;
    country: string;
    latitude: number;
    longitude: number;
    region?: string;
  } | null;
  status: 'known' | 'unknown';
  source: 'live' | 'simulation';
}
export interface PopLiveAdvisory {
  kind: 'window' | 'overdue' | 'mismatch' | 'observation_unknown';
  transition_id?: string | null;
  observed_pop_id?: string | null;
}
