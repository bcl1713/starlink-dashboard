export interface KaTransition {
  latitude: number;
  longitude: number;
  fromSatellite: string;
  toSatellite: string;
  timestamp: string;
}

export interface TimelineSegment {
  id: string;
  start_time: string;
  end_time: string;
  status: string;
  x_state?: string;
  ka_state?: string;
  ku_state?: string;
  reasons?: string[];
  latitude?: number;
  longitude?: number;
  metadata?: Record<string, unknown>;
}

export interface Timeline {
  mission_leg_id: string;
  created_at: string;
  segments: TimelineSegment[];
  advisories?: unknown[];
  statistics?: Record<string, unknown>;
}
