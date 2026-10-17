/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { useOperatorJournal } from './useOperatorJournal';
import { failure, health, input, page, record } from '@/test/operator-fixtures';
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
function mount() {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue(health);
  if (!vi.isMockFunction(api.readOperatorRecord))
    vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page().items[0]);
  const reads = vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  const hook = renderHook(() => useOperatorJournal('mission-a'), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    ),
  });
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
