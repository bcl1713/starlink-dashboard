export interface XBandTransition {
  id: string;
  latitude: number;
  longitude: number;
  target_satellite_id: string;
  target_beam_id?: string;
  is_same_satellite_transition?: boolean;
}

export interface KaOutage {
  id: string;                      // Unique identifier (required)
  start_time: string;              // ISO 8601 datetime string
  duration_seconds: number;        // Duration in seconds (required)
}

export interface KuOutageOverride {
  id: string;                      // Unique identifier (required)
  start_time: string;              // ISO 8601 datetime string
  duration_seconds: number;        // Duration in seconds (required)
  reason?: string;                 // Optional reason for outage
}

export interface SatelliteConfig {
  xband_starting_satellite?: string;
  xband_transitions: XBandTransition[];
  ka_outages: KaOutage[];
  ku_outages: KuOutageOverride[];
}
