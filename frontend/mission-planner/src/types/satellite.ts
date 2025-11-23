export interface XBandTransition {
  latitude: number;
  longitude: number;
  from_satellite: string;
  to_satellite: string;
  timestamp?: string;
}

export interface KaOutage {
  start_waypoint_index: number;
  end_waypoint_index: number;
  start_waypoint_name: string;
  end_waypoint_name: string;
  reason?: string;
}

export interface KuOutage {
  start_waypoint_index: number;
  end_waypoint_index: number;
  start_waypoint_name: string;
  end_waypoint_name: string;
  reason?: string;
}

export interface SatelliteConfig {
  xband_starting_satellite?: string;
  xband_transitions: XBandTransition[];
  ka_outages: KaOutage[];
  ku_outages: KuOutage[];
}
