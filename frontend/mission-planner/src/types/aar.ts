export interface AARSegment {
  id: string;
  start_waypoint_name: string;
  end_waypoint_name: string;
}

export interface AARConfig {
  segments: AARSegment[];
}
