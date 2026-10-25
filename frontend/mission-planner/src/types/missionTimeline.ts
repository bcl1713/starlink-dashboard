import type { OperationalEvent, SourceCapture } from './operatorEvents';

export interface MissionTimelineLeg {
  leg_id: string;
  name: string;
  coverage: 'available' | 'partial' | 'last_known' | 'unavailable';
  reason: string | null;
}

export interface MissionTimelineSnapshot {
  schema_version: 1;
  mission_id: string;
  store_id: string;
  api_epoch: string;
  source_mode: 'live' | 'simulation';
  simulation_run_id: string | null;
  as_of: string;
  generation: string;
  H: number;
  legs: MissionTimelineLeg[];
  sources: SourceCapture[];
  events: OperationalEvent[];
}
