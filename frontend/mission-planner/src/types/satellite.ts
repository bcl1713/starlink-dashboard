export interface XBandTransition {
  id: string;
  latitude: number;
  longitude: number;
  target_satellite_id: string;
  target_beam_id?: string;
  is_same_satellite_transition?: boolean;
}

export interface KaOutage {
  start_time: string;  // ISO 8601 datetime string
  end_time: string;    // ISO 8601 datetime string
  reason?: string;
}

export interface KuOutage {
  start_time: string;  // ISO 8601 datetime string
  end_time: string;    // ISO 8601 datetime string
  reason?: string;
}

export interface SatelliteConfig {
  xband_starting_satellite?: string;
  xband_transitions: XBandTransition[];
  ka_outages: KaOutage[];
  ku_outages: KuOutage[];
}
