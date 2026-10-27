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
    pop_id?: string | null;
    identity_source?: string;
    matched_cidr?: string | null;
    sampled_at?: string | null;
    lookup_at?: string | null;
    freshness?: 'fresh' | 'stale';
    discrepancy?: boolean;
    provider_geoip?: {
      source?: string;
      ip: string;
      city: string;
      country: string;
      region?: string;
      latitude: number;
      longitude: number;
      lookup_at?: string | null;
      freshness?: 'fresh' | 'stale';
    } | null;
  } | null;
  status: 'known' | 'unknown';
  source: 'live' | 'simulation';
  sampled_at?: string | null;
  lookup_at?: string | null;
  freshness?: 'fresh' | 'stale' | 'unknown';
}
export interface PopOccurrence {
  transition_id: string;
  disposition: 'pending' | 'observed' | 'superseded' | 'unconfirmed';
  expected_utc: string;
  window_start_utc: string;
  window_end_utc: string;
  from_city?: string | null;
  to_city?: string | null;
  observed_at?: string | null;
  timing_residual_seconds?: number | null;
}
export interface PopLiveAdvisory {
  kind: 'window' | 'overdue' | 'mismatch' | 'observation_unknown';
  transition_id?: string | null;
  observed_pop_id?: string | null;
}

export interface CallContinuityInterval {
  start_utc: string;
  end_utc: string;
  classification:
    | 'ordinary'
    | 'advisory'
    | 'x_fallback'
    | 'planned_outage'
    | 'existing_outage'
    | 'unknown';
  transition_ids: string[];
  usable_alternatives: string[];
  source_ids: string[];
}
export interface CallContinuityProjection {
  revision: string;
  intervals: CallContinuityInterval[];
  planned_communications_outage_seconds: number;
  pop_call_outage_seconds: number;
  longest_call_outage_seconds: number;
}
