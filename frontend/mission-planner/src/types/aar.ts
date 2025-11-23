export interface AARSegment {
  id: string;
  start_waypoint: string;
  end_waypoint: string;
}

export interface AARConfig {
  segments: AARSegment[];
}
