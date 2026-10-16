import type { ItineraryData } from './planning';
export interface ImportIssue {
  code: string;
  message: string;
  leg_id?: string | null;
  route_id?: string | null;
  field?: string | null;
  candidates: string[];
}
export interface RevisionConflict {
  field: string;
  baseline: unknown;
  current: unknown;
  incoming: unknown;
}
export interface ImportOperation {
  id: string;
  generation: number;
  state:
    | 'queued'
    | 'running'
    | 'needs_input'
    | 'ready'
    | 'committed'
    | 'cancelled'
    | 'failed';
  stage: string;
  mission_id: string;
  revision: boolean;
  deadline: string;
  issues: ImportIssue[];
  error: string | null;
  details: {
    ar_options?: Record<string, { value: string; label: string }[]>;
    itinerary?: ItineraryData;
    routes?: { id: string; name: string }[];
    revision?: {
      changes: string[];
      conflicts: RevisionConflict[];
      change_details?: {
        field: string;
        leg: string;
        current: unknown;
        incoming: unknown;
      }[];
      leg_names?: Record<string, string>;
    };
  };
}
