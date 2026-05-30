export interface AARSegment {
  id: string;
  start_waypoint_name: string;
  end_waypoint_name: string;
  override_start_time?: string | null;
  override_end_time?: string | null;
}

export interface AARConfig {
  segments: AARSegment[];
}
