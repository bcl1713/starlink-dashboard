export interface EventNotification {
  generation: string | null;
  severity_generation: number;
  acknowledged: boolean;
  acknowledged_at: string | null;
  retired: boolean;
  eligible: boolean;
  priority: number;
  threshold_at: string | null;
  acknowledgment_available: boolean;
  available: boolean;
  reason: string | null;
}
export interface OperationalEvent {
  schema_version: 1;
  event_id: string;
  mission_id: string;
  leg_id: string | null;
  kind:
    | 'call_prep'
    | 'call_start'
    | 'issue_followup'
    | 'pop_advisory'
    | 'restriction';
  title: string;
  due_at: string | null;
  end_at: string | null;
  state: 'upcoming' | 'active' | 'overdue' | 'inactive' | 'unknown';
  provenance: 'scheduled' | 'operator_reported' | 'modeled' | 'observed';
  source_ref: string | null;
  source_revision: string | null;
  source_captured_at: string | null;
  freshness: 'fresh' | 'stale' | 'unknown';
  confidence: string | null;
  transport: string | null;
  protected_participation_ids: string[];
  conference_ids: string[];
  transport_relevance: 'configured' | 'intended' | 'unknown' | 'call';
  continuity_status: 'modeled' | 'unknown';
  discrepancies: string[];
  significance:
    | 'routine'
    | 'advisory'
    | 'degraded'
    | 'unavailable'
    | 'call_outage';
  active: boolean;
  schedule_key: string;
  family_key: string;
  dependent_versions: Record<string, number>;
  notification: EventNotification;
}
export interface SourceCapture {
  source: string;
  revision: string | null;
  generation: string | null;
  input_identity: string | null;
  captured_at: string | null;
  freshness: 'fresh' | 'stale' | 'unknown' | 'disabled';
  aligned: boolean;
  guardable: boolean;
  reason: string | null;
}
export interface EventSnapshot {
  schema_version: 1;
  store_id: string;
  api_epoch: string;
  mission_id: string;
  source_mode: 'live' | 'simulation';
  simulation_run_id: string | null;
  as_of: string;
  H: number;
  generation: string;
  sources: SourceCapture[];
  coverage: 'available' | 'partial' | 'unknown';
  events: OperationalEvent[];
  snapshot_token: string;
  cursor: string | null;
  truncated: boolean;
}
export interface AckRequest {
  schema_version: 1;
  occurrence_id: string;
  severity_generation: number;
  snapshot_token: string;
}
export interface AckReceipt {
  schema_version: 1;
  receipt_type: 'event_acknowledgment';
  command_id: string;
  acknowledgment_id: string;
  occurrence_id: string;
  severity_generation: number;
  acknowledged_at: string;
  replayed: boolean;
}
