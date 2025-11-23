export interface XBandTransition {
  latitude: number;
  longitude: number;
  from_satellite: string;
  to_satellite: string;
  timestamp?: string;
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
