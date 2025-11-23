export interface AARSegment {
  id: string;
  name: string;
  start_waypoint_index: number;
  end_waypoint_index: number;
  start_waypoint_name: string;
  end_waypoint_name: string;
  altitude_feet?: number;
  notes?: string;
}

export interface AARConfig {
  segments: AARSegment[];
}
