/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { health, input, page, record } from '@/test/operator-fixtures';
import { useOperatorIssueDraft } from './useOperatorIssueDraft';
import { useOperatorJournal } from './useOperatorJournal';
const identity = {
  storeId: 'store',
  epoch: 'epoch-a',
  sourceMode: 'live',
  simulationRunId: null,
  missionId: 'mission-a',
  recordId: 'new',
};
const clients: QueryClient[] = [];
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  sessionStorage.clear();
  vi.restoreAllMocks();
});
it('reload restores unsent text and isolates mission and epoch', () => {
  const first = renderHook(() => useOperatorIssueDraft(identity, { text: '' }));
  act(() => first.result.current.setDraft({ text: 'Synthetic problem' }));
  first.unmount();
  const next = renderHook(() => useOperatorIssueDraft(identity, { text: '' }));
  expect(next.result.current.draft.text).toBe('Synthetic problem');
  const other = renderHook(() =>
    useOperatorIssueDraft({ ...identity, missionId: 'mission-b' }, { text: '' })
  );
  expect(other.result.current.draft.text).toBe('');
  const epoch = renderHook(() =>
    useOperatorIssueDraft({ ...identity, epoch: 'epoch-b' }, { text: '' })
  );
  expect(epoch.result.current.draft.text).toBe('');
  expect(
    [...Array(sessionStorage.length)].some((_, i) =>
      sessionStorage
        .getItem(sessionStorage.key(i)!)
        ?.includes('Synthetic problem')
    )
  ).toBe(true);
});
it('storage failure retains the in-memory draft with a visible error', () => {
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('quota');
  });
  const hook = renderHook(() => useOperatorIssueDraft(identity, { text: '' }));
  act(() => hook.result.current.setDraft({ text: 'Synthetic retained' }));
  expect(hook.result.current.draft.text).toBe('Synthetic retained');
  expect(hook.result.current.storageError).toBeTruthy();
});
function mount(epoch = 'epoch-a') {
  vi.spyOn(api, 'getOperatorHealth').mockResolvedValue({
    ...health,
    api_epoch: epoch,
  });
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(page());
  vi.spyOn(api, 'readOperatorRecord').mockResolvedValue(page().items[0]);
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  return renderHook(
    () => useOperatorJournal('mission-a', 'issue', { durable: true }),
    {
      wrapper: ({ children }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    }
  );
}
it('lost receipt and reload replay the frozen request and key once', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValueOnce(new Error('lost acknowledgment'))
    .mockResolvedValue({
      schema_version: 1,
      command_id: 'receipt',
      saved_records: [record],
    });
  const first = mount();
  await waitFor(() =>
    expect(first.result.current.health.data?.ready).toBe(true)
  );
  await act(async () => {
    await first.result.current.save({ operation: 'create', body: input });
  });
  const frozen = structuredClone(save.mock.calls[0]);
  first.unmount();
  const second = mount();
  await waitFor(() => expect(second.result.current.pending).toBeTruthy());
  await act(async () => {
    await second.result.current.retry();
  });
  expect(save.mock.calls[1]).toEqual(frozen);
  expect(second.result.current.pending).toBeNull();
});
it('older-epoch pending command is quarantined and cannot replay', async () => {
  const save = vi
    .spyOn(api, 'saveOperatorCommand')
    .mockRejectedValue(new Error('lost'));
  const first = mount();
  await waitFor(() =>
    expect(first.result.current.health.data?.ready).toBe(true)
  );
  await act(async () => {
    await first.result.current.save({ operation: 'create', body: input });
  });
  first.unmount();
  const second = mount('epoch-b');
  await waitFor(() => expect(second.result.current.blocked).toBe(true));
  await act(async () => {
    await second.result.current.retry();
  });
  expect(save).toHaveBeenCalledTimes(1);
});
