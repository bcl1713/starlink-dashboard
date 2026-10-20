import { expect, it } from 'vitest';
import { input, record } from '@/test/operator-fixtures';
import { DraftRegistry } from '../workspace/draftRegistry';
import { draftCommand, targetIdentity } from '../workspace/commandRegistry';
import {
  captureRetryObservation,
  collectRetryEvidence,
} from './trainingRetryEvidence';

const identity = {
  fixtureVersion: 1,
  origin: 'http://private',
  storeId: 'store',
  epoch: 'epoch-a',
  missionId: 'mission-a',
};
const namespace = 'operator-training:private';
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
    recordId: null,
    newDraftId: null,
    correctionVersion: null,
  },
  input
);
const request = {
  command: draftCommand(draft),
  key: 'frozen-key',
  epoch: identity.epoch,
  identity: targetIdentity(draft.target),
  workspace: {
    schemaVersion: 1 as const,
    draftId: draft.draftId,
    revision: 1,
    baseVersion: null,
    target: draft.target,
  },
};
const saved = {
  ...record,
  provenance: { ...record.provenance, source_mode: 'simulation' as const },
};
const attempts = [
  { id: 'first', request },
  { id: 'retry', request },
];
const receipt = {
  schema_version: 1 as const,
  command_id: saved.command_id,
  saved_records: [saved],
};
const uncertain = {
  commandId: request.key,
  status: 'uncertain' as const,
  pending: request,
};
const accepted = { ...uncertain, status: 'accepted' as const, receipt };
it('requires a backend version observed before exact retry and two actual attempts', () => {
  const observation = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [saved]
  );
  expect(observation).not.toBeNull();
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation!],
      attempts,
      [accepted],
      [saved]
    )
  ).toEqual(['lost-receipt-same-key']);
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation!],
      attempts.slice(0, 1),
      [accepted],
      [saved]
    )
  ).toEqual([]);
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation!],
      attempts,
      [accepted],
      []
    )
  ).toEqual([]);
});
it('does not credit a first attempt that never committed, a changed retry, or a different context', () => {
  const noCommit = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    []
  );
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [noCommit!],
      attempts,
      [accepted],
      [saved]
    )
  ).toEqual([]);
  const observation = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [saved]
  )!;
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation],
      [attempts[0], { id: 'retry', request: { ...request, key: 'different' } }],
      [accepted],
      [saved]
    )
  ).toEqual([]);
  expect(
    collectRetryEvidence(
      { ...identity, epoch: 'restored' },
      namespace,
      [observation],
      attempts,
      [accepted],
      [saved]
    )
  ).toEqual([]);
  expect(
    captureRetryObservation(identity, 'other', uncertain, attempts, [saved])
  ).toBeNull();
});
it('does not mistake an existing record ID for the committed update version', () => {
  const update = {
    ...request,
    command: {
      operation: 'update' as const,
      record_id: saved.record_id,
      body: { ...input, expected_version: 1 },
    },
    workspace: {
      ...request.workspace,
      baseVersion: 1,
      target: { ...draft.target, recordId: saved.record_id, newDraftId: null },
    },
  };
  const updated = {
    ...saved,
    version: 2,
    previous_version: 1,
    command_id: 'update-command',
    operation: 'update' as const,
  };
  const observed = captureRetryObservation(
    identity,
    namespace,
    { commandId: request.key, status: 'uncertain', pending: update },
    [{ id: 'one', request: update }],
    [saved]
  )!;
  const retryAttempts = [
    { id: 'one', request: update },
    { id: 'two', request: update },
  ];
  const acceptedUpdate = {
    commandId: request.key,
    status: 'accepted' as const,
    receipt: {
      ...receipt,
      command_id: updated.command_id,
      saved_records: [updated],
    },
  };
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observed],
      retryAttempts,
      [acceptedUpdate],
      [saved, updated]
    )
  ).toEqual([]);
});

it('rejects corrupt persisted requests and never mutates the captured request', () => {
  const observation = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [saved]
  )!;
  observation.request.key = 'changed';
  expect(request.key).toBe('frozen-key');
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation],
      attempts,
      [accepted],
      [saved]
    )
  ).toEqual([]);
  const invalid = { ...observation, request: { ...request, epoch: 'foreign' } };
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [invalid],
      attempts,
      [accepted],
      [saved]
    )
  ).toEqual([]);
});

it('retains raw accepted retry facts after the tray/attempt log retires, validated against full backend history', async () => {
  const { retainRetryReceipts } = await import('./trainingRetryEvidence');
  const observation = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [saved]
  )!;
  const retained = retainRetryReceipts(
    identity,
    namespace,
    [observation],
    attempts,
    [accepted],
    [saved]
  );
  expect(retained[0].replay!.receipt).toEqual(receipt);
  const resumed = JSON.parse(JSON.stringify(retained));
  expect(
    collectRetryEvidence(identity, namespace, resumed, [], [], [saved])
  ).toEqual(['lost-receipt-same-key']);
  expect(
    collectRetryEvidence(identity, namespace, resumed, [], [], [])
  ).toEqual([]);
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      resumed,
      [],
      [],
      [
        {
          ...saved,
          payload: {
            ...saved.payload,
            note: 'Contradictory immutable version',
          },
        },
      ]
    )
  ).toEqual([]);
  expect(
    collectRetryEvidence(
      { ...identity, epoch: 'restored' },
      namespace,
      resumed,
      [],
      [],
      [saved]
    )
  ).toEqual([]);
});
it('cannot turn an unrelated accepted write or corrupted persisted retry into proof', async () => {
  const { retainRetryReceipts } = await import('./trainingRetryEvidence');
  const unrelated = {
    ...saved,
    payload: { ...saved.payload, title: 'Different command body' },
  };
  const observation = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [unrelated]
  )!;
  const transaction = {
    ...accepted,
    receipt: { ...receipt, saved_records: [unrelated] },
  };
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation],
      attempts,
      [transaction],
      [unrelated]
    )
  ).toEqual([]);
  const original = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [saved]
  )!;
  const retained = retainRetryReceipts(
    identity,
    namespace,
    [original],
    attempts,
    [accepted],
    [saved]
  );
  retained[0].replay!.attempt.request.key = 'changed-on-disk';
  expect(
    collectRetryEvidence(identity, namespace, retained, [], [], [saved])
  ).toEqual([]);
});

it('matches canonical UTC representations without changing exact retry bytes or microseconds', () => {
  const observation = captureRetryObservation(
    identity,
    namespace,
    uncertain,
    attempts.slice(0, 1),
    [saved]
  )!;
  const normalized = {
    ...saved,
    time: { ...saved.time, occurred_at: '2026-10-17T10:11:12.123456+00:00' },
  };
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation],
      attempts,
      [{ ...accepted, receipt: { ...receipt, saved_records: [normalized] } }],
      [normalized]
    )
  ).toEqual(['lost-receipt-same-key']);
  const different = {
    ...normalized,
    time: { ...normalized.time, occurred_at: '2026-10-17T10:11:12.123457Z' },
  };
  expect(
    collectRetryEvidence(
      identity,
      namespace,
      [observation],
      attempts,
      [{ ...accepted, receipt: { ...receipt, saved_records: [different] } }],
      [different]
    )
  ).toEqual([]);
});
