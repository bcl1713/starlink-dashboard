import type { PayloadBase, RecordTime, SavedRecord, Scope } from './operator';
export type TransportValue = 'Starshield' | 'Ka' | 'X' | 'unknown';
export interface ReportTime {
  at: string | null;
  precision: 'exact' | 'approximate' | 'unknown';
}
export interface TransportChangeReport {
  transport: TransportValue;
  time: ReportTime;
}
export interface TransportCheck {
  time: ReportTime;
  result: 'satisfactory' | 'issue_reported' | 'unknown';
  note: string;
}
export interface TransportServiceRow {
  row_id: string;
  service: string;
  intended: { transport: TransportValue } | null;
  requested: TransportChangeReport | null;
  applied: TransportChangeReport | null;
  checked: TransportCheck | null;
}
export interface TransportDecisionPayload extends PayloadBase {
  entry_type: 'transport_decision';
  services: TransportServiceRow[];
  reason: string;
  call_id: string | null;
  conference_id: string | null;
}
export interface TransportDecisionInput {
  schema_version: 1;
  record_type: 'transport_decision';
  mission_id: string;
  leg_id: string | null;
  scope: Scope;
  time: RecordTime;
  payload: TransportDecisionPayload;
  operator_label?: string | null;
}
export interface TransportDraft {
  input: TransportDecisionInput;
  replacement_check_row_ids: string[];
}
export interface CommunicationWindow {
  record_id: string;
  version: number;
  leg_id: string | null;
  kind: 'call' | 'preparation' | 'conference' | 'connected';
  title: string;
  start_at: string | null;
  end_at: string | null;
  basis: 'scheduled' | 'operator_reported';
  call_id: string | null;
  conference_id: string | null;
  ongoing: boolean;
}
export interface TransportAssessment {
  decision_id: string;
  row_id: string;
  service: string;
  subject: 'change_vs_activity' | 'communications_vs_restriction';
  report_stage: 'intended' | 'requested' | 'applied' | 'unknown';
  transport: string | null;
  status: 'overlap' | 'possible_impact' | 'unknown' | 'no_overlap_found';
  message: string;
  activity_id: string | null;
  event_ids: string[];
  source_refs: string[];
  dependent_versions: Record<string, number>;
  time_basis: string | null;
  freshness: 'fresh' | 'stale' | 'unknown';
}
export interface TransportReviewData {
  as_of: string;
  H: number;
  actual_routing: 'unknown';
  coverage: 'available' | 'partial' | 'unknown';
  horizon_end_at: string;
  activities: CommunicationWindow[];
  assessments: TransportAssessment[];
}
export type SavedTransportDecision = SavedRecord & {
  payload: TransportDecisionPayload;
};
