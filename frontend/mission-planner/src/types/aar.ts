export interface AARSegment {
  id: string;
  name: string;
  start_waypoint: string;
  end_waypoint: string;
  altitude_feet?: number;
  notes?: string;
}

export interface AARConfig {
  segments: AARSegment[];
}
