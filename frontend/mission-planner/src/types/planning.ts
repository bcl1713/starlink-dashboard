/** Planning v1 JSON wire schemas. UTC timestamps are ISO-8601 strings. */
import type { Mission } from './mission';
import type { ManualAARTrack, ManualRouteSplice } from './aar';
import type { KaOutage, KuOutageOverride } from './satellite';

export type PlanningPolicy = 'prefer_starshield_v1';

export interface EvaluationContext {
  version?: 'planning_v1';
  input_identity: string;
  seed_times?: string[];
  candidate_times?: string[];
  boundaries?: string[];
  source_hashes?: Record<string, string>;
  height_profile?: HeightProfilePoint[];
  assumptions?: string[];
  candidate_cadence_seconds?: 60;
  interval_semantics?: 'half_open';
}

export interface HeightProfilePoint {
  timestamp: string;
  height_meters: number;
  source: 'confirmed_ar' | 'route' | 'cruise_fallback';
  assumption?: string | null;
}

export interface RouteAnchor {
  route_id: string;
  content_hash: string;
  segment_index: number;
  fraction: number;
  occurrence_id: string;
  source_time: string;
  latitude: number;
  longitude: number;
  timing_mode?: 'route_bound' | 'fixed_utc' | 'elapsed';
  elapsed_seconds?: number | null;
}

export interface PlanningError {
  code: string;
  message: string;
  field?: string | null;
  retryable?: boolean;
  action?: string | null;
  source_page?: number | null;
  source_row?: number | null;
}

export interface ItineraryAR {
  id: string;
  track: string;
  source_page?: number | null;
  source_row?: number | null;
  source_text?: string;
  entry_time: string;
  exit_time: string;
  source_time_precision: 'minute' | 'second';
  source_altitude?: number | null;
  confirmed_units?: 'flight_level' | 'feet' | 'meters' | null;
  start_anchor?: RouteAnchor | null;
  end_anchor?: RouteAnchor | null;
  match_status?: 'matched' | 'ambiguous' | 'unresolved' | 'excluded';
  confirmed?: boolean;
  exclusion_note?: string | null;
}

export interface AccessConfirmation {
  satellite_ids: string[];
  confirmed?: boolean;
  confirmed_at?: string | null;
}

export interface SatelliteSelection {
  permitted_satellite_ids?: string[];
  access_confirmation?: AccessConfirmation | null;
  starshield_enabled?: boolean;
}

export interface AnchoredSwap {
  id: string;
  target_satellite_id: string;
  anchor: RouteAnchor;
  target_beam_id?: string | null;
  origin?: 'manual' | 'generated';
}

export interface PlanningLock {
  id: string;
  target_satellite_id: string;
  anchor?: RouteAnchor | null;
  swap_id?: string | null;
  kind?: 'initial' | 'swap';
}

export interface PlanningDraft {
  no_ars_confirmed?: boolean;
  permitted_satellite_ids?: string[];
  access_confirmation?: AccessConfirmation | null;
  starshield_enabled?: boolean;
  initial_x_satellite_id?: string | null;
  swaps?: AnchoredSwap[];
  ar_corrections?: ItineraryAR[];
  manual_aar_tracks?: ManualAARTrack[];
  manual_route_splice?: ManualRouteSplice | null;
  ka_outages?: KaOutage[];
  ku_overrides?: KuOutageOverride[];
  adjusted_departure_time?: string | null;
  locks?: PlanningLock[];
  planning_policy?: 'prefer_starshield_v1';
  evaluation_context?: EvaluationContext | null;
}

export interface ReviewRecord {
  input_identity: string;
  confirmed_ar_ids?: string[];
  excluded_ar_ids?: string[];
  no_ars_confirmed?: boolean;
  satellite_plan_confirmed: boolean;
  gap_acknowledged?: boolean;
  saved_at: string;
}

export interface RouteBinding {
  route_id: string;
  source_id: string;
  content_hash: string;
  filename: string;
  ingestion_profile?: 'planning_v1';
}

export interface ExpectedLeg {
  id: string;
  ordinal: number;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string;
  arrival_time: string;
  ar_rows?: ItineraryAR[];
  ar_section_status?: 'listed' | 'empty' | 'unrecognized';
  route?: RouteBinding | null;
  draft?: PlanningDraft | null;
  review?: ReviewRecord | null;
  installed_leg_id?: string | null;
  retired?: boolean;
}

export interface SourceRevision {
  id: string;
  owner: string;
  kind: 'itinerary_pdf' | 'route_kml';
  filename: string;
  content_hash: string;
  expires_at?: string | null;
}

export interface PlanningSpan {
  start_time: string;
  end_time: string;
  reason: string;
  state?: 'available' | 'degraded' | 'offline';
  height_meters?: number | null;
  assumption?: string | null;
}

export interface SatellitePosition {
  satellite_id: string;
  latitude: number;
  longitude: number;
}

export interface PlanningInputSnapshot {
  version?: 'planning_v1';
  route_json: string;
  anchor_route_json: string;
  structural_draft_json: string;
  constraints_json: string;
  coverage_json?: string;
  ka_coverage_events_json?: string;
  ka_coverage_windows?: PlanningSpan[];
  start_time: string;
  end_time: string;
  ar_windows?: PlanningSpan[];
  overlays?: PlanningSpan[];
  ka_outages?: PlanningSpan[];
  ku_outages?: PlanningSpan[];
  safety_windows?: PlanningSpan[];
  satellites: SatellitePosition[];
  starshield_enabled: boolean;
  planning_policy?: PlanningPolicy;
  assumptions?: string[];
  unresolved?: string[];
}

export type PlanningInputs = PlanningInputSnapshot;

export interface EvaluationInterval {
  raw_constraints?: string[];
  latitude?: number | null;
  longitude?: number | null;
  altitude_meters?: number | null;
  heading_degrees?: number | null;
  start_time: string;
  end_time: string;
  satellite_id?: string | null;
  physical_x_state?: 'available' | 'degraded' | 'offline';
  physical_ka_state?: 'available' | 'degraded' | 'offline';
  physical_ku_state?: 'available' | 'degraded' | 'offline';
  policy_x_state?: 'available' | 'degraded' | 'offline';
  policy_ka_state?: 'available' | 'degraded' | 'offline';
  policy_ku_state?: 'available' | 'degraded' | 'offline';
  physical_reasons?: string[];
  policy_reasons?: string[];
  safety_reasons?: string[];
}

export interface BackupGap {
  start_time: string;
  end_time: string;
  reasons?: string[];
}

export interface PlanningEvaluation {
  context: EvaluationContext;
  intervals?: EvaluationInterval[];
  outage_seconds: number;
  swap_count: number;
  longest_gap_seconds: number;
  backup_gaps?: BackupGap[];
  errors?: PlanningError[];
}

export interface PlanningProposal {
  id: string;
  expected_revision: number;
  input_identity: string;
  context: EvaluationContext;
  proposed_draft?: PlanningDraft | null;
  baseline_evaluation?: PlanningEvaluation | null;
  candidate_evaluation?: PlanningEvaluation | null;
  state: 'ready' | 'failed' | 'stale';
  errors?: PlanningError[];
}

export interface PlanningManifest {
  schema_version?: 1;
  revision?: number;
  source_revisions?: SourceRevision[];
  expected_legs?: ExpectedLeg[];
  proposals?: PlanningProposal[];
  review_records?: ReviewRecord[];
  route_bindings?: RouteBinding[];
  route_history?: RouteBinding[];
}

export interface ExpectedLegCard {
  leg: ExpectedLeg;
  input_identity: string;
  computation_status?: 'idle' | 'calculating' | 'ready' | 'failed' | 'stale';
  errors?: PlanningError[];
  readonly review_status: 'awaiting_kml' | 'needs_review' | 'reviewed';
}

export interface PlanningView {
  mission: Mission;
  revision: number;
  expected_legs: ExpectedLegCard[];
  errors?: PlanningError[];
}

export interface SourceEvidence {
  source_id?: string | null;
  source_page: number;
  source_row: number;
  source_text: string;
  field?: string | null;
}

export interface ItineraryData {
  name: string;
  itinerary_revision?: number | null;
  aircraft?: string | null;
  call_sign?: string | null;
  expected_legs?: ExpectedLeg[];
}

export interface ItineraryPreview {
  preview_id: string;
  parsed_values?: ItineraryData | null;
  field_errors?: PlanningError[];
  source_evidence?: SourceEvidence[];
  source?: SourceRevision | null;
  confirmable?: boolean;
  expires_at: string;
}

export interface ARMatchCandidates {
  ar_id: string;
  start_candidates?: RouteAnchor[];
  end_candidates?: RouteAnchor[];
}

export interface RouteBindingPreview {
  preview_id: string;
  expected_revision: number;
  binding: RouteBinding;
  discrepancy_errors?: PlanningError[];
  matched_ar_candidates?: ARMatchCandidates[];
  expires_at: string;
}

export interface PlanningSatelliteOption {
  id: string;
  label: string;
  transport: 'X' | 'Ka' | 'Ku';
  latitude?: number | null;
  longitude?: number | null;
  eligible: boolean;
  error?: PlanningError | null;
}

export interface PlanningSatelliteOptions {
  satellites: PlanningSatelliteOption[];
}

export interface RevisionLegMapping {
  incoming_leg_id: string;
  expected_leg_id?: string | null;
  action: 'retain' | 'add' | 'retire';
}

export interface RevisionChange {
  field: string;
  expected_leg_id?: string | null;
  before?: string | null;
  after?: string | null;
  requires_resolution?: boolean;
}

export interface RevisionPreview {
  preview_id: string;
  parsed_values?: ItineraryData | null;
  field_errors?: PlanningError[];
  source_evidence?: SourceEvidence[];
  source?: SourceRevision | null;
  confirmable?: boolean;
  expires_at: string;
  expected_revision: number;
  input_identity: string;
  changes?: RevisionChange[];
  leg_mappings?: RevisionLegMapping[];
  lower_revision?: boolean;
  identical_content?: boolean;
}

export interface ConfirmItinerary {
  permitted_satellite_ids?: string[];
  access_confirmation?: AccessConfirmation | null;
  starshield_enabled?: boolean;
  preview_id: string;
  itinerary: ItineraryData;
  idempotency_key: string;
}

export interface RevisionRequest {
  expected_revision: number;
}

export interface AcceptRouteBinding {
  expected_revision: number;
  preview_id: string;
  discrepancy_acknowledgments?: string[];
}

export interface SaveDraft {
  expected_revision: number;
  draft: PlanningDraft;
  ar_section_status?: 'listed' | 'empty' | 'unrecognized' | null;
}

export interface PreviewDraft {
  expected_revision: number;
  draft: PlanningDraft;
  ar_section_status?: 'listed' | 'empty' | 'unrecognized' | null;
}

export interface GenerateProposal {
  expected_revision: number;
  input_identity: string;
}

export interface ApplyProposal {
  expected_revision: number;
  input_identity: string;
  proposal_id: string;
}

export interface SaveReviewed {
  expected_revision: number;
  input_identity: string;
  confirmed_ar_ids?: string[];
  excluded_ar_ids?: string[];
  no_ars_confirmed?: boolean;
  satellite_plan_confirmed: boolean;
  gap_acknowledged?: boolean;
}

export interface ApplyRevision {
  expected_revision: number;
  input_identity: string;
  preview_id: string;
  itinerary: ItineraryData;
  leg_mappings: RevisionLegMapping[];
  discrepancy_acknowledgments?: string[];
  allow_lower_revision?: boolean;
}
