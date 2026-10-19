/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { useOperatorJournal, type Pending } from './useOperatorJournal';
import { failure, health, input, page, record } from '@/test/operator-fixtures';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
function mount(options: Parameters<typeof useOperatorJournal>[2] = {}) {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  if (!vi.isMockFunction(api.readOperatorRecord))
    vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page().items[0]);
  const reads = vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  const hook = renderHook(
    () => useOperatorJournal('mission-a', 'journal_entry', options),
    {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    }
  );
  return { ...hook, reads };
}
it.each([
  new Error('lost acknowledgment'),
  failure(503, 'commit_outcome_unknown'),
])(
  'retries an immutable request after uncertainty and refetches latest after replay: %s',
  async (error) => {
    const save = vi
      .spyOn(api, 'saveOperatorCommand')
      .mockRejectedValueOnce(error)
      .mockResolvedValue({
        schema_version: 1,
        command_id: 'receipt',
        saved_records: [record],
      });
    const { result, reads } = mount();
    await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
    const draft = structuredClone(input);
    await act(async () => {
      await result.current.save({ operation: 'create', body: draft });
    });
    expect(result.current.pending).toBeTruthy();
    const original = structuredClone(save.mock.calls[0]);
    draft.payload.title = 'Edited after request';
    await act(async () => {
      await result.current.retry();
    });
    expect(save.mock.calls[1]).toEqual(original);
    expect(save.mock.calls[1][0].body).toEqual(input);
    expect(result.current.pending).toBeNull();
    await waitFor(() => expect(reads.mock.calls.length).toBeGreaterThan(1));
  }
);
it('shows latest on conflict and requires explicit reconciliation; epoch mismatch cannot replay', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(failure(409, 'version_conflict'))
    .mockRejectedValueOnce(failure(409, 'epoch_mismatch'));
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(
    page([{ ...record, version: 2 }]).items[0]
  );
  const { result } = mount();
  await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
  await act(async () => {
    await result.current.save({
      operation: 'update',
      record_id: record.record_id,
      body: { ...input, expected_version: 1 },
    });
  });
  expect(result.current.latest?.record.version).toBe(2);
  expect(result.current.blocked).toBe(true);
  await act(async () => {
    await result.current.retry();
  });
  expect(save).toHaveBeenCalledTimes(1);
  await act(async () => {
    await result.current.reconcile();
  });
  await act(async () => {
    await result.current.save({ operation: 'create', body: input });
  });
  expect(result.current.blocked).toBe(true);
  await act(async () => {
    await result.current.retry();
  });
  expect(save).toHaveBeenCalledTimes(2);
});
it('blocks an uncertain old request when health changes epoch before retry', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValue(new Error('lost acknowledgment'));
  const { result } = mount();
  await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
  await act(async () => {
    await result.current.save({ operation: 'create', body: input });
  });
  vi.mocked(api.getOperatorHealth).mockResolvedValue({
    ...health,
    api_epoch: 'epoch-b',
  });
  await act(async () => {
    await result.current.retry();
  });
  expect(save).toHaveBeenCalledTimes(1);
  expect(result.current.pending?.epoch).toBe('epoch-a');
  expect(result.current.blocked).toBe(true);
  await act(async () => {
    await result.current.retry();
  });
  expect(save).toHaveBeenCalledTimes(1);
});
it('returns latest current state separately from a replayed historical receipt', async () => {
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [record],
  });
  const { result, reads } = mount();
  await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
  const latest = {
    ...record,
    version: 3,
    payload: { ...record.payload, title: 'Later correction' },
  };
  reads.mockResolvedValue(page([latest]));
  vi.mocked(api.readOperatorRecord).mockResolvedValue(page([latest]).items[0]);
  let saved;
  await act(async () => {
    saved = await result.current.save({ operation: 'create', body: input });
  });
  expect(saved).toMatchObject({
    receipt: { saved_records: [record] },
    current: latest,
  });
});
it.each(['update', 'remove', 'restore'] as const)(
  'reconciles an uncertain %s absent in a replacement store without replaying it',
  async (operation) => {
    const save = vi
      .spyOn(api, 'saveOperatorCommand')
      .mockRejectedValueOnce(new Error('lost acknowledgment'))
      .mockResolvedValue({
        schema_version: 1,
        command_id: 'new',
        saved_records: [record],
      });
    const { result, reads } = mount();
    await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
    const command =
      operation === 'update'
        ? {
            operation,
            record_id: record.record_id,
            body: { ...input, expected_version: 1 },
          }
        : {
            operation,
            record_id: record.record_id,
            body: { schema_version: 1 as const, expected_version: 1 },
          };
    await act(async () => {
      await result.current.save(command);
    });
    const original = structuredClone(save.mock.calls[0]);
    vi.mocked(api.getOperatorHealth).mockResolvedValue({
      ...health,
      api_epoch: 'epoch-b',
    });
    reads.mockResolvedValue(page([]));
    vi.mocked(api.readOperatorRecord).mockRejectedValue(
      failure(404, 'record_not_found')
    );
    await act(async () => {
      await result.current.retry();
    });
    await act(async () => {
      expect(await result.current.reconcile()).toBe(false);
    });
    expect(result.current.missingInNewStore).toBe(true);
    expect(save).toHaveBeenCalledTimes(1);
    expect(result.current.pending?.command).toEqual(command);
    act(() => {
      expect(result.current.recoverMissing()).toBe(true);
    });
    expect(result.current.pending).toBeNull();
    expect(result.current.blocked).toBe(false);
    await act(async () => {
      await result.current.retry();
    });
    expect(save).toHaveBeenCalledTimes(1);
    await act(async () => {
      await result.current.save({ operation: 'create', body: input });
    });
    expect(save.mock.calls[1][0]).toEqual({ operation: 'create', body: input });
    expect(save.mock.calls[1][1]).not.toBe(original[1]);
    expect(save.mock.calls[1][2]).toBe('epoch-b');
  }
);
it('retains the conflict target after failed latest reads until a targeted reread succeeds', async () => {
  vi.spyOn(api, 'saveOperatorCommand').mockRejectedValue(
    failure(409, 'version_conflict')
  );
  const target = vi
    .spyOn(api, 'readOperatorRecord')
    .mockRejectedValue(failure(503, 'busy'));
  const { result } = mount();
  await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
  await act(async () => {
    await result.current.save({
      operation: 'update',
      record_id: record.record_id,
      body: { ...input, expected_version: 1 },
    });
  });
  expect(result.current.pending).toBeNull();
  expect(result.current.latest).toBeNull();
  expect(result.current.reconcileError).toMatch(/could not be read/);
  await act(async () => {
    expect(await result.current.reconcile()).toBe(false);
  });
  expect(result.current.blocked).toBe(true);
  const latest = { ...record, version: 3 };
  target.mockResolvedValue(page([latest]).items[0]);
  await act(async () => {
    expect(await result.current.reconcile()).toEqual({ current: latest });
  });
  expect(target.mock.calls).toEqual([
    [record.record_id],
    [record.record_id],
    [record.record_id],
  ]);
  expect(result.current.blocked).toBe(false);
});
it('partitions calls from journal reads and refreshes independently loaded summaries after a call save', async () => {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  const call = {
    ...record,
    record_type: 'call' as const,
    payload: {
      ...record.payload,
      entry_type: 'call' as const,
      status: 'completed' as const,
      conference_id: null,
      prep_lead_minutes: null,
    },
  };
  const reads = vi
    .spyOn(api, 'readOperatorRecords')
    .mockResolvedValue(page([call]));
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page([call]).items[0]);
  vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'call-receipt',
    saved_records: [call],
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  client.setQueryData(
    ['operator-brief', 'mission-a', 'independent'],
    page([call])
  );
  const hook = renderHook(() => useOperatorJournal('mission-a', 'call'), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
  await waitFor(() => expect(hook.result.current.records.data).toBeTruthy());
  expect(reads.mock.calls[0][0].record_type).toBe('call');
  await act(async () => {
    await hook.result.current.save({
      operation: 'create',
      body: { ...input, record_type: 'call', payload: call.payload },
    });
  });
  expect(hook.result.current.saved).toBe(true);
  expect(
    client.getQueryState(['operator-brief', 'mission-a', 'independent'])
      ?.isInvalidated
  ).toBe(true);
});

it('observes actual send attempts without allowing observation to alter the transaction', async () => {
  const save = vi.spyOn(api, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [record],
  });
  const observe = vi.fn((request: Pending) => {
    request.key = 'observer-mutated-key';
    if (request.command.operation === 'create')
      request.command.body.payload.title = 'Observer mutated title';
    throw new Error('Observer failure');
  });
  const { result } = mount({ onAttempt: observe });
  await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
  await act(async () => {
    await result.current.save({
      operation: 'create',
      body: structuredClone(input),
    });
  });
  expect(observe).toHaveBeenCalledTimes(1);
  expect(save.mock.calls[0][0].body).toEqual(input);
  expect(save.mock.calls[0][1]).not.toBe('observer-mutated-key');
  expect(result.current.saved).toBe(true);
  expect(result.current.error).toBeNull();
});
it('observes both frozen attempts of a genuinely uncertain send and its exact retry', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('Receipt lost'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
  const observe = vi.fn();
  const { result } = mount({ onAttempt: observe });
  await waitFor(() => expect(result.current.health.data?.ready).toBe(true));
  await act(async () => {
    await result.current.save({
      operation: 'create',
      body: structuredClone(input),
    });
  });
  await act(async () => {
    await result.current.retry();
  });
  expect(save).toHaveBeenCalledTimes(2);
  expect(observe).toHaveBeenCalledTimes(2);
  expect(observe.mock.calls[1][0]).toEqual(observe.mock.calls[0][0]);
});
