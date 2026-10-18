/** @vitest-environment jsdom */
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useLayoutEffect } from 'react';
import * as api from '@/services/operator';
import * as eventApi from '@/services/operatorEvents';
import { health, input, page, record, failure } from '@/test/operator-fixtures';
import {
  OperatorWorkspaceProvider,
  useOperatorWorkspace,
} from './OperatorWorkspaceProvider';
import { DraftRegistry } from './draftRegistry';
import type { DraftTarget } from './types';
import {
  commandLane,
  loadPendingOwners,
  pendingPrefix,
} from './commandRegistry';

const clients: QueryClient[] = [];
let workspace: ReturnType<typeof useOperatorWorkspace>;
let navigate: ReturnType<typeof useNavigate>;
const target: DraftTarget = {
  storeId: health.store_id!,
  epoch: health.api_epoch!,
  sourceMode: health.source_mode,
  simulationRunId: health.simulation_run_id,
  missionId: input.mission_id,
  recordType: input.record_type,
  recordId: null,
  newDraftId: null,
  scope: input.scope,
  legId: input.leg_id,
  previousLegId: input.payload.previous_leg_id,
  nextLegId: input.payload.next_leg_id,
  correctionVersion: null,
};

function ObserveWorkspace() {
  const value = useOperatorWorkspace();
  useLayoutEffect(() => {
    workspace = value;
  });
  return null;
}
function Probe() {
  const value = useOperatorWorkspace();
  const go = useNavigate();
  useLayoutEffect(() => {
    workspace = value;
    navigate = go;
  });
  return <p>Operator page</p>;
}
function mount(registry = new DraftRegistry(sessionStorage)) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  client.setQueryData(['operator-health'], health);
  clients.push(client);
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/operator?workspace=1']}>
        <OperatorWorkspaceProvider registry={registry}>
          <ObserveWorkspace />
          <Routes>
            <Route path="/operator" element={<Probe />} />
            <Route path="/missions" element={<p>Missions page</p>} />
          </Routes>
        </OperatorWorkspaceProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { ...result, client, registry };
}
async function submit(draftId: string) {
  let pending!: Promise<void>;
  act(() => {
    pending = workspace.submitDraft(draftId);
  });
  await act(async () => {
    await pending;
  });
}
beforeEach(() => {
  sessionStorage.clear();
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page().items[0]);
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  vi.restoreAllMocks();
});

it('route unmount to Missions during save preserves late receipt and newer revision', async () => {
  let resolve!: (value: {
    schema_version: 1;
    command_id: string;
    saved_records: (typeof record)[];
  }) => void;
  const save = vi.spyOn(api, 'saveOperatorCommand').mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r;
      })
  );
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  let submission!: Promise<void>;
  await act(async () => {
    workspace.openDraft(draft.draftId);
    submission = workspace.submitDraft(draft.draftId);
  });
  await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
  await act(async () => {
    registry.editDraft(draft.draftId, {
      ...input,
      payload: { ...input.payload, title: 'newer input' },
    });
    navigate('/missions');
  });
  expect(screen.queryByText('Operator page')).toBeNull();
  await act(async () => {
    resolve({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
    await submission;
  });
  expect(registry.resumeDraft(draft.draftId)?.input.payload.title).toBe(
    'newer input'
  );
  await act(async () => navigate('/operator?workspace=1'));
  expect(
    workspace.tray.some((row) => row.receipt?.command_id === 'receipt')
  ).toBe(true);
});

it('lost receipt retry preserves exact body key time and does not auto-send on remount', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('lost receipt'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
  const { registry, unmount } = mount();
  const draft = registry.createDraft(target, input);
  await submit(draft.draftId);
  const original = structuredClone(save.mock.calls[0]);
  unmount();
  mount(new DraftRegistry(sessionStorage));
  await waitFor(() => expect(workspace.tray).toHaveLength(1));
  expect(save).toHaveBeenCalledTimes(1);
  await act(async () => workspace.retryExact(workspace.tray[0].commandId));
  expect(save.mock.calls[1]).toEqual(original);
});

it('storage rejection before send retains input without dispatch', async () => {
  const save = vi.spyOn(api, 'saveOperatorCommand');
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('full');
  });
  await submit(draft.draftId);
  expect(save).not.toHaveBeenCalled();
  expect(registry.resumeDraft(draft.draftId)?.input).toEqual(input);
  expect(workspace.tray[0].status).toBe('storage_error');
});

it('accepted receipt with failed current read is distinct from an uncertain write', async () => {
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [record],
  });
  vi.mocked(api.readOperatorRecord).mockRejectedValue(
    new Error('read unavailable')
  );
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  await submit(draft.draftId);
  expect(workspace.tray[0].status).toBe('accepted_unreadable');
  expect(workspace.tray[0].receipt?.command_id).toBe('receipt');
  expect(registry.resumeDraft(draft.draftId)).toBeNull();
});

it('409 and failed latest read retain draft for explicit reconciliation', async () => {
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    failure(409, 'version_conflict')
  );
  vi.mocked(api.readOperatorRecord).mockRejectedValue(
    new Error('read unavailable')
  );
  const { registry } = mount();
  const draft = registry.createDraft(
    { ...target, recordId: record.record_id },
    input
  );
  registry.parkDraft({ ...draft, baseVersion: 1, baseRecord: record });
  await submit(draft.draftId);
  expect(workspace.tray[0].status).toBe('needs_review');
  expect(workspace.tray[0].message).toContain('could not be read');
  expect(registry.resumeDraft(draft.draftId)).not.toBeNull();
});

it('store rotation quarantines uncertain command and never resends it', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValue(new Error('uncertain'));
  const { registry, client } = mount();
  const draft = registry.createDraft(target, input);
  await submit(draft.draftId);
  vi.mocked(api.getOperatorHealth).mockResolvedValue({
    ...health,
    api_epoch: 'epoch-b',
  });
  await act(async () => {
    client.setQueryData(['operator-health'], {
      ...health,
      api_epoch: 'epoch-b',
    });
  });
  await act(async () => workspace.retryExact(workspace.tray[0].commandId));
  expect(save).toHaveBeenCalledTimes(1);
  expect(workspace.tray[0].status).toBe('quarantined');
});

it('another draft in the same lane cannot replace an uncertain save', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValue(new Error('uncertain'));
  const { registry } = mount();
  const first = registry.createDraft(target, input);
  const second = registry.createDraft(target, {
    ...input,
    payload: { ...input.payload, title: 'second' },
  });
  await submit(first.draftId);
  const frozen = workspace.tray[0].pending;
  await submit(second.draftId);
  expect(save).toHaveBeenCalledTimes(1);
  expect(workspace.tray[0].pending).toEqual(frozen);
  expect(workspace.tray[0].draftId).toBe(first.draftId);
});

it('late receipt on another mission updates its named tray and retains the other draft', async () => {
  let release!: (value: {
    schema_version: 1;
    command_id: string;
    saved_records: (typeof record)[];
  }) => void;
  vi.spyOn(api, 'saveOperatorCommand').mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve;
      })
  );
  const { registry } = mount();
  const first = registry.createDraft(target, input);
  const other = registry.createDraft(
    { ...target, missionId: 'mission-b' },
    { ...input, mission_id: 'mission-b' }
  );
  let pending!: Promise<void>;
  act(() => {
    pending = workspace.submitDraft(first.draftId);
  });
  await waitFor(() => expect(api.saveOperatorCommand).toHaveBeenCalledTimes(1));
  act(() => workspace.openDraft(other.draftId));
  await act(async () => {
    release({
      schema_version: 1,
      command_id: 'late-a',
      saved_records: [record],
    });
    await pending;
  });
  expect(workspace.selectedDraftId).toBe(other.draftId);
  expect(workspace.tray[0].target.missionId).toBe('mission-a');
  expect(workspace.tray[0].receipt?.command_id).toBe('late-a');
  expect(registry.resumeDraft(other.draftId)).not.toBeNull();
});

it('frozen workspace envelope is persisted before the only mutation dispatch', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockImplementation(async (command, key, epoch) => {
      const storageKey = Object.keys(sessionStorage).find((key) =>
        key.startsWith('operator-workspace-pending:v1:')
      )!;
      const retained = JSON.parse(sessionStorage.getItem(storageKey)!);
      expect(retained.command).toEqual(command);
      expect(retained.key).toBe(key);
      expect(retained.epoch).toBe(epoch);
      expect(retained.workspace.revision).toBe(1);
      return {
        schema_version: 1,
        command_id: 'receipt',
        saved_records: [record],
      };
    });
  const { registry } = mount();
  await submit(registry.createDraft(target, input).draftId);
  expect(save).toHaveBeenCalledTimes(1);
});

it('command supplied by an editor cannot cross the pinned mission target', async () => {
  const save = vi.spyOn(api, 'saveOperatorCommand');
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  let pending!: Promise<void>;
  act(() => {
    pending = workspace.submitDraft(draft.draftId, {
      command: {
        operation: 'create',
        body: { ...input, mission_id: 'mission-b' },
      },
    });
  });
  await act(async () => {
    await pending;
  });
  expect(save).not.toHaveBeenCalled();
  expect(workspace.tray[0].status).toBe('failed');
});

it.each([
  'record_id',
  'scope',
  'leg_id',
  'previous_leg_id',
  'next_leg_id',
  'expected_version',
])('quarantines a recovered update with mismatched %s', (field) => {
  const savedTarget = {
    ...target,
    recordId: record.record_id,
    newDraftId: null,
  };
  const command = {
    operation: 'update',
    record_id: record.record_id,
    body: { ...structuredClone(input), expected_version: 1 },
  };
  if (field === 'record_id') command.record_id = 'wrong-record';
  else if (field === 'scope') command.body.scope = 'postflight';
  else if (field === 'leg_id') command.body.leg_id = 'wrong-leg';
  else if (field === 'expected_version') command.body.expected_version = 9;
  else
    command.body.payload[field as 'previous_leg_id' | 'next_leg_id'] =
      'wrong-leg';
  const key = pendingPrefix + commandLane(savedTarget);
  const value = JSON.stringify({
    command,
    key: 'client-key',
    epoch: health.api_epoch,
    identity: JSON.stringify([
      health.store_id,
      health.api_epoch,
      health.source_mode,
      health.simulation_run_id,
    ]),
    workspace: {
      schemaVersion: 1,
      draftId: 'draft-a',
      revision: 1,
      baseVersion: 1,
      target: savedTarget,
    },
  });
  sessionStorage.setItem(key, value);
  const loaded = loadPendingOwners(sessionStorage);
  expect(loaded.requests).toEqual([]);
  expect(loaded.errors).toHaveLength(1);
  expect(sessionStorage.getItem(key)).toBe(value);
});
it('prepares a lifecycle command with the backend clock before freezing and dispatching it', async () => {
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'clock-command',
    saved_records: [record],
  });
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  let submission!: Promise<void>;
  act(() => {
    submission = workspace.submitDraft(draft.draftId, {
      atCurrentTime: (now) => ({
        operation: 'create',
        body: { ...input, time: { ...input.time, occurred_at: now } },
      }),
    });
  });
  await act(async () => {
    await submission;
  });
  expect(save.mock.calls[0][0]).toMatchObject({
    body: { time: { occurred_at: page().as_of } },
  });
});
it('rejects a changed historical correction target before dispatch', async () => {
  const { issueInput } = await import('../issueForms');
  const issue = issueInput('mission-a');
  issue.payload.corrects_version = 2;
  const { registry } = mount();
  const saved = { ...record, ...issue, record_type: 'issue' as const };
  const draft = registry.createDraft(
    {
      ...target,
      recordType: 'issue',
      recordId: record.record_id,
      correctionVersion: 2,
    },
    issue,
    saved
  );
  const command = {
    operation: 'update' as const,
    record_id: record.record_id,
    body: {
      ...issue,
      expected_version: 1,
      payload: { ...issue.payload, corrects_version: 3 },
    },
  };
  const { assertCommandTarget } = await import('./commandRegistry');
  expect(() => assertCommandTarget(draft, command)).toThrow(
    /correction target/
  );
});
it('delegates one health polling owner between the workspace and application navigation', async () => {
  mount();
  expect(workspace.ownsHealth).toBe(true);
  await act(async () => navigate('/missions'));
  expect(workspace.ownsHealth).toBe(false);
});
it('marks the submitted mission event snapshot stale after a receipt without starting another event owner', async () => {
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'refresh-events',
    saved_records: [record],
  });
  const read = vi.spyOn(eventApi, 'readEventSnapshot');
  const { registry, client } = mount();
  const identity = JSON.stringify([
    health.store_id,
    health.api_epoch,
    health.source_mode,
    health.simulation_run_id,
  ]);
  const key = ['operator-events', input.mission_id, identity];
  client.setQueryDefaults(['operator-events'], { gcTime: Infinity });
  client.setQueryData(key, { snapshot: {}, receivedAt: 0 });
  await submit(registry.createDraft(target, input).draftId);
  expect(save).toHaveBeenCalledOnce();
  expect(client.getQueryState(key)?.isInvalidated).toBe(true);
  expect(read).not.toHaveBeenCalled();
});
it('exposes independent snapshots of actual command attempts with their pinned targets', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  await submit(draft.draftId);
  expect(workspace.attempts).toHaveLength(1);
  const attempt = workspace.attempts[0];
  expect(attempt.request.workspace?.target).toEqual(draft.target);
  expect(attempt.request.key).toBe(save.mock.calls[0][1]);
  if (attempt.request.command.operation === 'create')
    attempt.request.command.body.payload.title = 'Changed observation copy';
  expect(save.mock.calls[0][0].body).toEqual(input);
});
it('keeps distinct actual retry observations without creating a second write owner', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('Receipt lost'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
  const { registry } = mount();
  const draft = registry.createDraft(target, input);
  await submit(draft.draftId);
  expect(workspace.attempts).toHaveLength(1);
  const key = workspace.tray[0].commandId;
  await act(async () => workspace.retryExact(key));
  expect(workspace.attempts).toHaveLength(2);
  expect(workspace.attempts[0].id).not.toBe(workspace.attempts[1].id);
  expect(workspace.attempts[0].request).toEqual(workspace.attempts[1].request);
  expect(save).toHaveBeenCalledTimes(2);
});
it('reuses the complete pending-envelope validator for read-only command evidence', async () => {
  const { decodePendingEnvelope, targetIdentity } = await import(
    './commandRegistry'
  );
  const registry = new DraftRegistry(sessionStorage);
  const draft = registry.createDraft(target, input);
  const request = {
    command: { operation: 'create' as const, body: draft.input },
    key: 'captured-key',
    epoch: draft.target.epoch,
    identity: targetIdentity(draft.target),
    workspace: {
      schemaVersion: 1 as const,
      draftId: draft.draftId,
      revision: draft.revision,
      baseVersion: null,
      target: draft.target,
    },
  };
  expect(decodePendingEnvelope(request)).toEqual(request);
  expect(() =>
    decodePendingEnvelope({
      ...request,
      command: {
        ...request.command,
        body: { ...request.command.body, scope: 'preflight' },
      },
    })
  ).toThrow();
  expect(() =>
    decodePendingEnvelope({ ...request, epoch: 'wrong-epoch' })
  ).toThrow();
});
