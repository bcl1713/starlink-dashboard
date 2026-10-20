import { z } from 'zod';
import type { SavedRecord } from '@/types/operator';
import type { TrainingIdentity } from './trainingProgress';
import { sameJson } from './trainingRecordIdentity';
import {
  decodePendingEnvelope,
  type TransactionTrayItem,
} from '../workspace/commandRegistry';
import { sameInputValue } from './trainingRetryReceipt';

const text = z.string().min(1),
  integer = z.number().int().nonnegative();
const health = z
  .object({
    ready: z.literal(true),
    store_id: text,
    api_epoch: text,
    source_mode: z.literal('simulation'),
    simulation_run_id: text,
    clock_regression: z.literal(false),
  })
  .passthrough();
const marker = z
  .object({ store_id: text, api_epoch: text, status: z.literal('ready') })
  .passthrough();
const saved = z.custom<SavedRecord>((value) => {
  const row = value as SavedRecord | null;
  return (
    !!row &&
    typeof row.record_id === 'string' &&
    typeof row.mission_id === 'string' &&
    typeof row.command_id === 'string' &&
    Number.isInteger(row.version) &&
    row.version > 0 &&
    Number.isInteger(row.journal_seq) &&
    row.journal_seq > 0 &&
    row.provenance?.source_mode === 'simulation'
  );
});
const rows = z.array(saved).max(5000);
const manifest = z
  .object({
    store_id: text,
    source_mode: z.literal('simulation'),
    simulation_run_id: text,
    schema_version: z.number().int().positive(),
    H: integer,
    database: text,
    checksum: z.string().regex(/^[0-9a-f]{64}$/),
    created_at: text,
    publication_sequence: integer,
  })
  .passthrough();
const inspection = z.object({
  manifest,
  databaseSha256: text,
  identity: marker,
  records: rows,
  history: rows,
  restoreReport: z
    .object({
      restored_H: integer,
      previous_H: integer,
      backup_created_at: text,
      preserved: text,
      api_epoch: text,
    })
    .nullable(),
  preservedIdentity: marker.nullable(),
});
const snapshot = z.object({
  health,
  H: integer,
  records: rows,
  history: rows,
  missions: z.array(z.object({ id: text }).passthrough()).max(9),
});
const schema = z.object({
  browserOrigin: text,
  nativeManifest: text,
  beforeBackup: snapshot,
  backup: inspection,
  beforeRestore: snapshot,
  afterRestore: snapshot,
  restoredBackup: inspection,
  restoreHealth: health,
  checkHealth: health,
  quarantinedRequests: z
    .array(
      z.object({
        request: z.unknown(),
        failure: z.object({ code: z.literal('epoch_mismatch') }).passthrough(),
        observedEpoch: text,
      })
    )
    .max(8)
    .default([]),
});
export type RecoveryObservation = z.infer<typeof schema>;
const ordered = (values: readonly SavedRecord[]) =>
  [...values].sort((a, b) => a.journal_seq - b.journal_seq);
const sameRows = (a: readonly SavedRecord[], b: readonly SavedRecord[]) =>
  sameJson(ordered(a), ordered(b));

/** Raw private tooling artifacts are cross-checked again against current API history. */
export function decodeRecoveryObservation(
  value: unknown,
  identity: TrainingIdentity,
  namespace?: string
): RecoveryObservation {
  const report = schema.parse(value);
  const {
    beforeBackup: first,
    beforeRestore: before,
    afterRestore: after,
    backup,
    restoredBackup: restored,
  } = report;
  const run = namespace ?? after.health.simulation_run_id;
  const native = restored.restoreReport;
  if (
    !/^operator-training-v1-[0-9a-f-]{36}$/.test(run) ||
    report.browserOrigin !== identity.origin ||
    ![
      first.health,
      before.health,
      after.health,
      report.restoreHealth,
      report.checkHealth,
    ].every(
      (h) => h.store_id === identity.storeId && h.simulation_run_id === run
    ) ||
    after.health.api_epoch !== identity.epoch ||
    report.restoreHealth.api_epoch !== identity.epoch ||
    report.checkHealth.api_epoch !== identity.epoch ||
    first.health.api_epoch !== before.health.api_epoch ||
    before.health.api_epoch === identity.epoch ||
    backup.identity.store_id !== identity.storeId ||
    restored.identity.store_id !== identity.storeId ||
    backup.identity.api_epoch !== before.health.api_epoch ||
    restored.identity.api_epoch !== identity.epoch ||
    !restored.preservedIdentity ||
    !sameJson(restored.preservedIdentity, backup.identity) ||
    !sameJson(backup.manifest, restored.manifest) ||
    backup.manifest.store_id !== identity.storeId ||
    backup.manifest.simulation_run_id !== run ||
    backup.databaseSha256 !== backup.manifest.checksum ||
    restored.databaseSha256 !== backup.manifest.checksum ||
    !native ||
    native.restored_H !== after.H ||
    native.previous_H !== before.H ||
    native.api_epoch !== identity.epoch ||
    native.backup_created_at !== backup.manifest.created_at ||
    !/^preserved-[A-Za-z0-9-]+$/.test(native.preserved) ||
    first.H !== backup.manifest.H ||
    after.H !== first.H ||
    before.H <= first.H ||
    !sameRows(first.records, backup.records) ||
    !sameRows(first.history, backup.history) ||
    !sameRows(after.records, backup.records) ||
    !sameRows(after.history, backup.history) ||
    !sameRows(restored.records, backup.records) ||
    !sameRows(restored.history, backup.history) ||
    !first.history.every(
      (row) =>
        row.journal_seq <= first.H &&
        before.history.some((other) => sameJson(row, other))
    ) ||
    !before.history.some(
      (row) => row.journal_seq > first.H && row.journal_seq <= before.H
    ) ||
    ![first, before, after].every(
      (s) =>
        s.records.every((row) => row.mission_id === identity.missionId) &&
        s.history.every((row) => row.mission_id === identity.missionId) &&
        s.missions.some((m) => m.id === identity.missionId)
    )
  )
    throw new Error(
      'Native backup/restore evidence does not match this private store and epoch.'
    );
  for (const quarantined of report.quarantinedRequests) {
    const request = decodePendingEnvelope(quarantined.request);
    const target = request.workspace.target;
    if (
      quarantined.observedEpoch !== identity.epoch ||
      request.epoch !== before.health.api_epoch ||
      target.epoch !== before.health.api_epoch ||
      target.storeId !== identity.storeId ||
      target.missionId !== identity.missionId ||
      target.sourceMode !== 'simulation' ||
      target.simulationRunId !== run
    )
      throw new Error(
        'Quarantined request does not retain this restore’s original epoch.'
      );
  }
  return report;
}

export function retainRecoveryObservation(
  identity: TrainingIdentity,
  namespace: string,
  value: unknown,
  tray: readonly TransactionTrayItem[]
): RecoveryObservation | undefined {
  if (value === undefined) return undefined;
  const report = decodeRecoveryObservation(value, identity, namespace);
  for (const row of tray) {
    if (
      row.status !== 'quarantined' ||
      row.retryReady ||
      !row.pending ||
      row.failure?.code !== 'epoch_mismatch'
    )
      continue;
    if (
      row.pending.workspace.target.epoch !==
      report.beforeRestore.health.api_epoch
    )
      continue;
    if (
      report.quarantinedRequests.some(
        (item) => decodePendingEnvelope(item.request).key === row.pending!.key
      )
    )
      continue;
    report.quarantinedRequests = [
      ...report.quarantinedRequests,
      {
        request: JSON.parse(JSON.stringify(row.pending)),
        failure: { ...row.failure, code: 'epoch_mismatch' as const },
        observedEpoch: identity.epoch,
      },
    ].slice(-8);
  }
  return decodeRecoveryObservation(report, identity, namespace);
}

export function collectRecoveryEvidence(
  identity: TrainingIdentity,
  namespace: string,
  H: number,
  records: readonly SavedRecord[],
  value: unknown
): string[] {
  if (value === undefined) return [];
  try {
    const report = decodeRecoveryObservation(value, identity, namespace);
    const boundary = report.afterRestore.H;
    const versions = new Map<string, SavedRecord>();
    for (const row of records) {
      const key = `${row.record_id}:${row.version}`;
      if (versions.has(key) && !sameJson(versions.get(key), row)) return [];
      versions.set(key, row);
    }
    const restored = [...versions.values()].filter(
      (row) => row.journal_seq <= boundary
    );
    if (H < boundary || !sameRows(restored, report.afterRestore.history))
      return [];
    // A replay of the discarded command is a new history revision and cannot
    // restore the original command's old epoch. Its original sequence is absent.
    const discarded = report.beforeRestore.history.filter(
      (row) => row.journal_seq > boundary
    );
    if (
      records.some((row) =>
        discarded.some((old) => row.command_id === old.command_id)
      )
    )
      return [];
    const outcomes = ['private-backup-restored'];
    if (
      report.quarantinedRequests.some((item) => {
        const request = decodePendingEnvelope(item.request);
        if (request.command.operation !== 'create') return false;
        const body = request.command.body;
        return discarded.some(
          (row) =>
            row.version === 1 &&
            row.record_type === body.record_type &&
            row.scope === body.scope &&
            row.leg_id === body.leg_id &&
            sameInputValue(body.time, row.time) &&
            sameInputValue(body.payload, row.payload)
        );
      })
    )
      outcomes.push('epoch-change-quarantine');
    return outcomes;
  } catch {
    return [];
  }
}
