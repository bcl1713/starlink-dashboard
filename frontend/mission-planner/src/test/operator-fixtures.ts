import type {
  JournalInput,
  OperatorHealth,
  RecordPage,
  SavedRecord,
} from '@/types/operator';
export const health: OperatorHealth = {
  schema_version: 1,
  enabled: true,
  ready: true,
  store_id: 'store',
  api_epoch: 'epoch-a',
  source_mode: 'live',
  simulation_run_id: null,
  clock_regression: false,
  error_code: null,
};
export const input: JournalInput = {
  schema_version: 1,
  record_type: 'journal_entry',
  mission_id: 'mission-a',
  leg_id: null,
  scope: 'mission',
  time: {
    occurred_at: '2026-10-17T10:11:12.123456Z',
    ended_at: null,
    precision: 'approximate',
    end_state: 'instant',
    planned_start_at: null,
    planned_end_at: null,
  },
  payload: {
    schema_version: 1,
    entry_type: 'note',
    title: 'Original',
    note: 'Retain me',
    previous_leg_id: null,
    next_leg_id: null,
  },
};
export const record: SavedRecord = {
  ...input,
  record_id: 'record-a',
  version: 1,
  previous_version: null,
  journal_seq: 1,
  command_id: 'command-a',
  operation: 'create',
  reason: null,
  reason_origin: null,
  deleted: false,
  recorded_at: '2026-10-17T11:00:00.000000Z',
  author: { backend: 'restricted-access operator', operator_label: null },
  provenance: {
    kind: 'operator_reported',
    source_mode: 'live',
    observed_at: null,
    predicted_at: null,
    source_ref: null,
    mutation_origin: 'interactive',
  },
};
export const page = (records = [record]): RecordPage => ({
  schema_version: 1,
  items: records.map((record) => ({
    schema_version: 1,
    record,
    association: {
      status: 'resolved',
      unresolved_fields: [],
      error_code: null,
    },
    freshness: {
      status: 'unknown',
      threshold_seconds: null,
      as_of: '2026-10-17T11:00:00.000000Z',
    },
  })),
  cursor: null,
  H: 1,
  as_of: '2026-10-17T11:00:00.000000Z',
});
export const failure = (status: number, code: string) =>
  Object.assign(new Error(code), {
    cause: {
      response: {
        status,
        data: { error: { code, message: code, retryable: status === 503 } },
      },
    },
  });
