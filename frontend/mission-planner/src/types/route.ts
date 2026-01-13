export interface RoutePoint {
  latitude: number;
  longitude: number;
  altitude?: number;
}

export interface TimingProfile {
  [key: string]: string | number;
}

export interface RouteDetail {
  id: string;
  name: string;
  description?: string;
  waypoint_count?: number;
  active?: boolean;
  created_at?: string;
  updated_at?: string;
  points?: RoutePoint[];
  timing_profile?: TimingProfile;
  flight_phase?: string;
}
