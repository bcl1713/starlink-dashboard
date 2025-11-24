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
  x_transitions?: unknown[];
  ka_outages?: unknown[];
  aar_windows?: unknown[];
  ku_overrides?: unknown[];
}

export interface MissionLeg {
  id: string;
  name: string;
  route_id: string;
  description?: string;
  transports: TransportConfig;
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
