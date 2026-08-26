export interface AARSegment {
  id: string;
  start_waypoint_name: string;
  end_waypoint_name: string;
  override_start_time?: string | null;
  override_end_time?: string | null;
  override_start_elapsed?: string | null;
}

export interface ManualAARTrackPoint {
  latitude: number;
  longitude: number;
}

export interface ManualAARTrack {
  id: string;
  name: string;
  points: ManualAARTrackPoint[];
}

/** Persisted operator input only; derived preview geometry is never saved. */
export interface ManualRouteSplice {
  enabled_track_id: string;
  leave_segment_index?: number;
  leave_fraction?: number;
  rejoin_segment_index?: number;
  rejoin_fraction?: number;
  speed_knots?: number;
}

export interface AARConfig {
  segments: AARSegment[];
  manualTracks: ManualAARTrack[];
}
