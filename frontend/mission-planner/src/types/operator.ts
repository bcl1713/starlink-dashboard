import type {
  TransportDecisionInput,
  TransportDecisionPayload,
} from './operatorTransport';
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
  | 'transport_report'
  | 'transport_decision';
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
export interface CallPayload extends PayloadBase {
  entry_type: 'call';
  status: 'tentative' | 'scheduled' | 'delayed' | 'completed' | 'cancelled';
  conference_id: string | null;
  party?: string | null;
  coordinator?: string | null;
  communications_kind?: 'voice' | 'vtc' | 'other' | null;
  prep_lead_minutes?: number | null;
}
export interface CallInput
  extends Omit<JournalInput, 'record_type' | 'payload'> {
  record_type: 'call';
  payload: CallPayload & { prep_lead_minutes: number | null };
}
export type Transport = 'Starshield' | 'Ka' | 'X';
export interface ConferencePayload extends PayloadBase {
  entry_type: 'conference';
  status?:
    | 'unknown'
    | 'preparing'
    | 'established'
    | 'interrupted'
    | 'closed'
    | null;
  coordinator?: string | null;
  verified_at?: string | null;
  intended_transport?: Transport | null;
  configured_transport?: Transport | null;
  configuration_reported_at?: string | null;
}
export interface ParticipationPayload extends PayloadBase {
  entry_type: 'participation';
  call_id: string | null;
  conference_id: string | null;
  participant?: string | null;
  state?: 'unknown' | 'connected' | 'interrupted' | 'left' | null;
  resumes_participation_id?: string | null;
}
export interface ConferenceInput
  extends Omit<JournalInput, 'record_type' | 'payload'> {
  record_type: 'conference';
  payload: ConferencePayload;
}
export interface ParticipationInput
  extends Omit<JournalInput, 'record_type' | 'payload'> {
  record_type: 'participation';
  payload: ParticipationPayload;
}
export interface IssuePayload extends PayloadBase {
  entry_type: 'issue';
  status: 'open' | 'monitoring' | 'resolved' | 'reopened';
  priority?: 'low' | 'normal' | 'high' | 'urgent' | null;
  mitigation?: 'none_reported' | 'mitigated' | 'workaround' | 'unknown';
  functional_area?: string | null;
  responsible_party?: string | null;
  follow_up_at?: string | null;
  update_text?: string;
  capability_id?: string | null;
  call_id?: string | null;
  conference_id?: string | null;
  transport?: Transport | null;
  corrects_version?: number | null;
  corrected_update_at?: string | null;
}
export interface CapabilityPayload extends PayloadBase {
  entry_type: 'capability_assessment';
  functional_status: 'unknown' | 'functional' | 'degraded' | 'unavailable';
  redundancy_status: 'unknown' | 'available' | 'degraded' | 'unavailable';
  functional_observed_at: string | null;
  redundancy_observed_at: string | null;
  functional_time_precision: 'exact' | 'approximate' | 'unknown';
  redundancy_time_precision: 'exact' | 'approximate' | 'unknown';
}
export interface IssueInput
  extends Omit<JournalInput, 'record_type' | 'payload'> {
  record_type: 'issue';
  payload: IssuePayload;
}
export interface CapabilityInput extends Omit<JournalInput, 'payload'> {
  payload: CapabilityPayload;
}
export interface IssueFollowup {
  record_id: string;
  version: number;
  follow_up_at: string | null;
  as_of: string | null;
  state:
    | 'inactive'
    | 'unscheduled'
    | 'upcoming'
    | 'due'
    | 'overdue'
    | 'unknown';
}
export type OperatorInput =
  | TransportDecisionInput
  | IssueInput
  | CapabilityInput
  | JournalInput
  | CallInput
  | ConferenceInput
  | ParticipationInput;
export type OperatorPayload =
  | TransportDecisionPayload
  | JournalPayload
  | CallPayload
  | ConferencePayload
  | ParticipationPayload
  | (PayloadBase & { entry_type: 'risk' })
  | IssuePayload
  | CapabilityPayload
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
  | { operation: 'create'; body: OperatorInput }
  | {
      operation: 'update';
      record_id: string;
      body: OperatorInput & {
        expected_version: number;
        replacement_check_row_ids?: string[];
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
  follow_up?: IssueFollowup;
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
