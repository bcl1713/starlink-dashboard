export type Scope =
  | 'mission'
  | 'preflight'
  | 'leg'
  | 'between_legs'
  | 'postflight';
export type Operation = 'create' | 'update' | 'remove' | 'restore';
export type RecordType =
  | 'journal_entry'
  | 'call'
  | 'conference'
  | 'participation'
  | 'issue'
  | 'risk'
  | 'transport_report';
export interface RecordTime {
  occurred_at: string | null;
  ended_at: string | null;
  precision: 'exact' | 'approximate' | 'unknown';
  end_state: 'instant' | 'ongoing' | 'known' | 'unknown';
  planned_start_at: string | null;
  planned_end_at: string | null;
}
export interface PayloadBase {
  schema_version: 1;
  title: string;
  note: string;
  previous_leg_id: string | null;
  next_leg_id: string | null;
}
export interface JournalPayload extends PayloadBase {
  entry_type: 'note' | 'call_observation';
}
export type OperatorPayload =
  | JournalPayload
  | (PayloadBase & {
      entry_type: 'call';
      status: 'scheduled' | 'completed' | 'cancelled';
      conference_id: string | null;
    })
  | (PayloadBase & { entry_type: 'conference' | 'risk' })
  | (PayloadBase & {
      entry_type: 'participation';
      call_id: string | null;
      conference_id: string | null;
    })
  | (PayloadBase & { entry_type: 'issue'; status: 'open' | 'resolved' })
  | (PayloadBase & {
      entry_type: 'transport_report';
      transport: 'Starshield' | 'Ka' | 'X';
      status:
        | 'reported_available'
        | 'reported_degraded'
        | 'reported_unavailable'
        | 'unknown';
    });
export interface JournalInput {
  schema_version: 1;
  record_type: 'journal_entry';
  mission_id: string;
  leg_id: string | null;
  scope: Scope;
  time: RecordTime;
  payload: JournalPayload;
  operator_label?: string | null;
}
export interface JournalTransition {
  schema_version: 1;
  expected_version: number;
  audit_note?: string | null;
  operator_label?: string | null;
}
export type OperatorCommand =
  | { operation: 'create'; body: JournalInput }
  | {
      operation: 'update';
      record_id: string;
      body: JournalInput & {
        expected_version: number;
        audit_note?: string | null;
      };
    }
  | {
      operation: 'remove' | 'restore';
      record_id: string;
      body: JournalTransition;
    };
export interface SavedRecord
  extends Omit<JournalInput, 'record_type' | 'payload' | 'operator_label'> {
  record_type: RecordType;
  payload: OperatorPayload;
  record_id: string;
  version: number;
  previous_version: number | null;
  journal_seq: number;
  command_id: string;
  operation: Operation;
  reason: string | null;
  reason_origin: 'automatic' | 'operator' | null;
  deleted: boolean;
  recorded_at: string;
  author: { backend: string; operator_label: string | null };
  provenance: {
    kind: 'operator_reported' | 'observed' | 'modeled';
    source_mode: 'live' | 'simulation';
    observed_at: string | null;
    predicted_at: string | null;
    source_ref: {
      producer_id: string;
      record_id: string | null;
      revision: string | null;
      fingerprint: string | null;
    } | null;
    mutation_origin: 'interactive' | 'retrospective' | 'source_sync';
  };
}
export interface ReadRecord {
  schema_version: 1;
  record: SavedRecord;
  association: {
    status: 'resolved' | 'missing' | 'unknown';
    unresolved_fields: string[];
    error_code: string | null;
  };
  freshness: {
    status: 'fresh' | 'stale' | 'unknown';
    threshold_seconds: number | null;
    as_of: string;
  };
}
export interface RecordPage {
  schema_version: 1;
  items: ReadRecord[];
  cursor: string | null;
  H: number;
  as_of: string;
}
export type HistoryPage = RecordPage;
export interface RecordFilters {
  mission_id: string;
  scope?: Scope;
  leg_id?: string;
  record_type?: RecordType;
  include_removed?: boolean;
}
export interface CommandReceipt {
  schema_version: 1;
  command_id: string;
  saved_records: SavedRecord[];
}
export interface OperatorHealth {
  schema_version: 1;
  enabled: boolean;
  ready: boolean;
  store_id: string | null;
  api_epoch: string | null;
  source_mode: 'live' | 'simulation';
  simulation_run_id: string | null;
  clock_regression: boolean;
  error_code: string | null;
}
export interface OperatorFailure {
  status?: number;
  code: string;
  message: string;
  retryable: boolean;
  fields?: Record<string, string>;
  current_version?: number;
  record_ids?: string[];
}
