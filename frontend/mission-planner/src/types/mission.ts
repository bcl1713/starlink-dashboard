import { SatelliteConfig } from './satellite';
import { AARConfig } from './aar';

export interface Mission {
  id: string;
  name: string;
  description?: string;
  legs: MissionLeg[];
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface MissionLeg {
  id: string;
  name: string;
  route_id?: string;
  description?: string;
  satellite_config?: SatelliteConfig;
  aar_config?: AARConfig;
  created_at: string;
  updated_at: string;
}

export interface CreateMissionRequest {
  id: string;
  name: string;
  description?: string;
  legs?: MissionLeg[];
}
