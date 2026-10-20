import { expect, it } from 'vitest';
import { input, record } from '@/test/operator-fixtures';
import { DraftRegistry } from '../workspace/draftRegistry';
import {
  draftCommand,
  commandLane,
  targetIdentity,
} from '../workspace/commandRegistry';
import {
  collectConflictEvidence,
  retainConflictObservations,
} from './trainingConflictEvidence';
const identity = {
  origin: 'http://private',
  fixtureVersion: 1,
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
const namespace = 'operator-training-v1-cc098a03-573a-4a89-ad78-167690ba631e';
const first = {
  ...record,
  provenance: { ...record.provenance, source_mode: 'simulation' as const },
};
const peer = {
  ...first,
  version: 2,
  previous_version: 1,
  journal_seq: 2,
  operation: 'update' as const,
  command_id: 'server-peer',
  payload: { ...first.payload, note: 'Actual counterpart edit' },
};
const saved = {
  ...first,
  version: 3,
  previous_version: 2,
  journal_seq: 3,
  operation: 'update' as const,
  command_id: 'server-reviewed',
};
const registry = new DraftRegistry(null);
const draft = registry.createDraft(
  {
    storeId: identity.storeId,
    epoch: identity.epoch,
    sourceMode: 'simulation',
    simulationRunId: namespace,
    missionId: identity.missionId,
    recordType: input.record_type,
    scope: input.scope,
    legId: null,
    previousLegId: null,
    nextLegId: null,
    recordId: first.record_id,
    newDraftId: null,
    correctionVersion: null,
  },
  input,
  first
);
const request = {
  key: 'client-rejected-key',
  epoch: identity.epoch,
  identity: targetIdentity(draft.target),
  command: draftCommand(draft),
  workspace: {
    schemaVersion: 1 as const,
    draftId: draft.draftId,
    revision: 1,
    baseVersion: 1,
    target: draft.target,
  },
};
const replacement = {
  ...request,
  key: 'client-reviewed-key',
  command: {
    operation: 'update' as const,
    record_id: first.record_id,
    body: { ...input, expected_version: 2 },
  },
  workspace: { ...request.workspace, revision: 2, baseVersion: 2 },
};
const attempts = [
  { id: 'failed-attempt', request },
  { id: 'reviewed-attempt', request: replacement },
];
const failure = {
  status: 409,
  code: 'version_conflict',
  message: 'Version changed',
  retryable: false,
  current_version: 2,
};
const conflict = {
  lane: commandLane(draft.target),
  commandId: request.key,
  draftId: draft.draftId,
  submittedRevision: 1,
  target: draft.target,
  status: 'needs_review' as const,
  title: 'Retained edit',
  message: 'Version changed',
  failure,
};
const receipt = {
  schema_version: 1 as const,
  command_id: saved.command_id,
  saved_records: [saved],
};
const backend = [first, peer, saved];
const collect = (reads: unknown, records = backend) =>
  collectConflictEvidence(identity, namespace, 3, records, reads);
it('requires the real conflict attempt, a reread and a distinct reviewed command with a matching saved revision', () => {
  let reads = retainConflictObservations(
    identity,
    namespace,
    [],
    [conflict],
    attempts.slice(0, 1),
    [first, peer]
  );
  expect(reads).toHaveLength(1);
  expect(collect(reads)).toEqual([]);
  reads = retainConflictObservations(
    identity,
    namespace,
    reads,
    [{ ...conflict, current: peer }],
    attempts.slice(0, 1),
    backend
  );
  expect(collect(reads)).toEqual([]);
  reads = retainConflictObservations(
    identity,
    namespace,
    reads,
    [
      {
        ...conflict,
        commandId: replacement.key,
        submittedRevision: 2,
        status: 'accepted',
        receipt,
        current: saved,
      },
    ],
    attempts,
    backend
  );
  expect(collect(JSON.parse(JSON.stringify(reads)))).toEqual([
    'real-conflict-reconciled',
  ]);
  expect(collect(reads, [first, saved])).toEqual([]);
});
it('rejects generic UI flags, foreign identities, missing attempts and a replacement that reuses the stale key or version', () => {
  expect(collect([{ passed: true }])).toEqual([]);
  expect(
    retainConflictObservations(identity, namespace, [], [conflict], [], backend)
  ).toEqual([]);
  const reads = retainConflictObservations(
    identity,
    namespace,
    [],
    [{ ...conflict, current: peer }],
    attempts,
    backend
  );
  for (const changed of [
    { ...identity, epoch: 'new-epoch' },
    { ...identity, origin: 'http://foreign' },
  ])
    expect(
      collectConflictEvidence(changed, namespace, 3, backend, reads)
    ).toEqual([]);
  const accepted = {
    ...conflict,
    status: 'accepted' as const,
    receipt,
    current: saved,
    submittedRevision: 2,
  };
  const sameKey = { ...replacement, key: request.key };
  expect(
    collect(
      retainConflictObservations(
        identity,
        namespace,
        reads,
        [accepted],
        [{ id: 'bad-attempt', request: sameKey }],
        backend
      )
    )
  ).toEqual([]);
});
