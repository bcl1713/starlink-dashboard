export interface ExportProgress {
  status: 'preparing' | 'exporting' | 'complete' | 'error';
  message: string;
  progress?: number;
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
