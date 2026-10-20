import type {
  OperatorInput,
  RecordType,
  SavedRecord,
  Scope,
} from '@/types/operator';

export interface DraftTarget {
  storeId: string;
  epoch: string;
  sourceMode: 'live' | 'simulation';
  simulationRunId: string | null;
  missionId: string;
  recordType: RecordType;
  recordId: string | null;
  newDraftId: string | null;
  scope: Scope;
  legId: string | null;
  previousLegId: string | null;
  nextLegId: string | null;
  correctionVersion: number | null;
}

export interface PersistenceResult {
  state: 'durable' | 'memory_only';
  message: string | null;
}

export interface DraftEnvelope {
  schemaVersion: 1;
  draftId: string;
  target: DraftTarget;
  baseRecord: SavedRecord | null;
  baseVersion: number | null;
  input: OperatorInput;
  revision: number;
  persistence: PersistenceResult;
  /** Editor-only choices (e.g. current time or correction text), never commands. */
  editorState?: Record<string, unknown>;
  legacyKey?: string;
  legacyFingerprint?: string;
}

export interface RecoveryResult {
  migratedDraftIds: string[];
  quarantinedKeys: string[];
  errors: { key: string; message: string }[];
}
