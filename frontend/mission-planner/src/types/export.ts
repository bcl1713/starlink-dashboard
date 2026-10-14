export interface ExportProgress {
  status: 'preparing' | 'exporting' | 'complete' | 'error';
  message: string;
  progress?: number;
}

export interface MissionExportDownload {
  blob: Blob;
  briefingStatus?: 'included' | 'omitted';
  warningCode?: string;
}

export interface ImportValidationError {
  field: string;
  message: string;
}

export interface ImportResult {
  success: boolean;
  mission_id?: string;
  errors?: ImportValidationError[];
  warnings?: string[];
}

export interface ExportPreparation {
  id: string;
  mission_id: string;
  state:
    | 'queued'
    | 'preparing'
    | 'ready'
    | 'failed'
    | 'cancelled'
    | 'superseded'
    | 'expired';
  fingerprint: string;
  revision?: number | null;
  stage: string;
  leg_states: Record<string, string>;
  queued_at: number;
  started_at?: number | null;
  finished_at?: number | null;
  deadline: number;
  expires_at?: number | null;
  error_code?: string | null;
  warning_code?: string | null;
  download_url?: string | null;
}
