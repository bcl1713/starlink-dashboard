import type { XBandTransition, KaOutage, KuOutageOverride } from './satellite';
import type { AARSegment } from './aar';

export interface Mission {
  id: string;
  name: string;
  description?: string;
  legs: MissionLeg[];
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface TransportConfig {
  initial_x_satellite_id: string;
  initial_ka_satellite_ids?: string[];
  x_transitions?: XBandTransition[];
  ka_outages?: KaOutage[];
  aar_windows?: AARSegment[];
  ku_overrides?: KuOutageOverride[];
}

export interface MissionLeg {
  id: string;
  name: string;
  route_id: string;
  description?: string;
  transports: TransportConfig;
  adjusted_departure_time?: string | null;
  created_at?: string;
  updated_at?: string;
  is_active?: boolean;
  notes?: string;
}

export interface CreateMissionRequest {
  id: string;
  name: string;
  description?: string;
  legs?: MissionLeg[];
}

export interface UpdateMissionRequest {
  name?: string;
  description?: string;
}

export interface UpdateLegRouteResponse {
  leg: MissionLeg;
  warnings?: string[] | null;
}

export interface UpdateLegResponse {
  leg: MissionLeg;
  warnings?: string[] | null;
}
