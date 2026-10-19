import { expect, it } from 'vitest';
import { health, input, record } from '@/test/operator-fixtures';
import {
  collectRecoveryEvidence,
  decodeRecoveryObservation,
  retainRecoveryObservation,
} from './trainingRecoveryEvidence';
import { DraftRegistry } from '../workspace/draftRegistry';
import {
  commandLane,
  draftCommand,
  targetIdentity,
} from '../workspace/commandRegistry';

const namespace = 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const identity = {
  origin: 'http://localhost',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-b',
  missionId: 'mission-a',
};
const saved = {
  ...record,
  provenance: { ...record.provenance, source_mode: 'simulation' as const },
};
const beforeHealth = {
  ...health,
  source_mode: 'simulation' as const,
  simulation_run_id: namespace,
};
const afterHealth = { ...beforeHealth, api_epoch: 'epoch-b' };
const snapshot = (apiHealth = beforeHealth, records = [saved]) => ({
  health: apiHealth,
  H: records.length,
  records,
  history: records,
  missions: [{ id: 'mission-a' }],
});
const marker = (api_epoch: string) => ({
  store_id: 'store',
  api_epoch,
  source_mode: 'simulation',
  simulation_run_id: namespace,
  status: 'ready',
});
const manifest = {
  store_id: 'store',
  source_mode: 'simulation',
  simulation_run_id: namespace,
  schema_version: 2,
  H: 1,
  database: 'backup-a.sqlite3',
  checksum: 'a'.repeat(64),
  created_at: '2026-10-17T16:00:00Z',
  publication_sequence: 1,
};
const backup = {
  manifest,
  databaseSha256: manifest.checksum,
  identity: marker('epoch-a'),
  records: [saved],
  history: [saved],
  restoreReport: null,
  preservedIdentity: null,
};
const lost = {
  ...saved,
  record_id: 'lost',
  journal_seq: 2,
  command_id: 'lost-command',
};
const report = () => ({
  browserOrigin: identity.origin,
  nativeManifest: '/app/data/operator/simulation/private/backups/backup-a.json',
  beforeBackup: snapshot(),
  backup,
  beforeRestore: snapshot(beforeHealth, [saved, lost]),
  afterRestore: snapshot(afterHealth),
  restoreHealth: afterHealth,
  checkHealth: afterHealth,
  restoredBackup: {
    ...backup,
    identity: marker('epoch-b'),
    preservedIdentity: marker('epoch-a'),
    restoreReport: {
      restored_H: 1,
      previous_H: 2,
      backup_created_at: manifest.created_at,
      preserved: 'preserved-a',
      api_epoch: 'epoch-b',
    },
  },
});
it('requires native restore artifacts and fresh immutable restored history, without carrying old guide completion across epochs', () => {
  const observation = decodeRecoveryObservation(report(), identity, namespace);
  expect(
    collectRecoveryEvidence(identity, namespace, 1, [saved], observation)
  ).toEqual(['private-backup-restored']);
  expect(
    collectRecoveryEvidence(identity, namespace, 1, [saved, saved], observation)
  ).toEqual(['private-backup-restored']);
  expect(
    collectRecoveryEvidence(identity, namespace, 1, [], observation)
  ).toEqual([]);
  expect(
    collectRecoveryEvidence(identity, namespace, 2, [saved, lost], observation)
  ).toEqual([]);
  expect(() =>
    decodeRecoveryObservation(
      report(),
      { ...identity, epoch: 'epoch-a' },
      namespace
    )
  ).toThrow();
});
it('rejects a changed checksum, absent post-backup revision, foreign identity or forged preserved epoch', () => {
  for (const mutate of [
    (value: ReturnType<typeof report>) => {
      value.restoredBackup.databaseSha256 = 'b'.repeat(64);
    },
    (value: ReturnType<typeof report>) => {
      value.beforeRestore = snapshot();
    },
    (value: ReturnType<typeof report>) => {
      value.browserOrigin = 'https://foreign.example';
    },
    (value: ReturnType<typeof report>) => {
      value.restoredBackup.preservedIdentity.api_epoch = 'epoch-b';
    },
    (value: ReturnType<typeof report>) => {
      value.restoredBackup.restoreReport.previous_H = 99;
    },
  ]) {
    const value = structuredClone(report());
    mutate(value);
    expect(() =>
      decodeRecoveryObservation(value, identity, namespace)
    ).toThrow();
  }
});
it('credits epoch quarantine only for a frozen old request matching the discarded committed revision', () => {
  const registry = new DraftRegistry(null);
  const draft = registry.createDraft(
    {
      storeId: 'store',
      epoch: 'epoch-a',
      sourceMode: 'simulation',
      simulationRunId: namespace,
      missionId: identity.missionId,
      recordType: 'journal_entry',
      scope: 'mission',
      legId: null,
      previousLegId: null,
      nextLegId: null,
      recordId: null,
      newDraftId: 'draft-lost',
      correctionVersion: null,
    },
    input
  );
  const request = {
    key: 'frozen-client-key',
    epoch: 'epoch-a',
    identity: targetIdentity(draft.target),
    command: draftCommand(draft),
    workspace: {
      schemaVersion: 1 as const,
      draftId: draft.draftId,
      revision: draft.revision,
      baseVersion: null,
      target: draft.target,
    },
  };
  const row = {
    lane: commandLane(draft.target),
    commandId: request.key,
    draftId: draft.draftId,
    submittedRevision: draft.revision,
    target: draft.target,
    title: 'Lost receipt',
    status: 'quarantined' as const,
    message: 'Store changed',
    retryReady: false,
    pending: request,
    failure: {
      code: 'epoch_mismatch',
      message: 'Store changed',
      retryable: false,
    },
  };
  const retained = retainRecoveryObservation(identity, namespace, report(), [
    row,
  ]);
  expect(
    collectRecoveryEvidence(identity, namespace, 1, [saved], retained)
  ).toEqual(['private-backup-restored', 'epoch-change-quarantine']);
  expect(retained?.quarantinedRequests[0].request).toEqual(request);
  const enabled = retainRecoveryObservation(identity, namespace, report(), [
    { ...row, retryReady: true },
  ]);
  expect(
    collectRecoveryEvidence(identity, namespace, 1, [saved], enabled)
  ).toEqual(['private-backup-restored']);
});
