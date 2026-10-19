/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operatorEvents';
import { eventSnapshot } from '@/test/operator-event-fixtures';
import { useOperatorEvents } from './useOperatorEvents';
const clients: QueryClient[] = [];
const identity = JSON.stringify(['store', 'epoch-a', 'live', null]);
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
function wrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}
it('keeps a lost acknowledgment frozen across reload and retries the same key and token', async () => {
  vi.spyOn(api, 'readEventSnapshot').mockResolvedValue(eventSnapshot());
  const post = vi
    .spyOn(api, 'acknowledgeOperatorEvent')
    .mockRejectedValueOnce(new Error('Lost receipt'))
    .mockResolvedValueOnce({
      schema_version: 1,
      receipt_type: 'event_acknowledgment',
      command_id: 'command',
      acknowledgment_id: 'ack',
      occurrence_id: 'occurrence-a',
      severity_generation: 2,
      acknowledged_at: '2026-10-17T16:00:00Z',
      replayed: false,
    });
  const first = renderHook(() => useOperatorEvents('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(first.result.current.snapshot).toBeDefined());
  await act(async () => {
    await first.result.current.acknowledge(
      first.result.current.snapshot!.events[0]
    );
  });
  expect(first.result.current.pendingAcknowledgment).toBeTruthy();
  const request = post.mock.calls[0];
  first.unmount();
  const second = renderHook(() => useOperatorEvents('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() =>
    expect(second.result.current.pendingAcknowledgment).toBeTruthy()
  );
  await act(async () => {
    await second.result.current.retryAcknowledgment();
  });
  expect(post.mock.calls[1]).toEqual(request);
  expect(second.result.current.pendingAcknowledgment).toBeNull();
});
it('aborts the old mission and never publishes a late snapshot into its replacement', async () => {
  let release!: (value: ReturnType<typeof eventSnapshot>) => void;
  const get = vi
    .spyOn(api, 'readEventSnapshot')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve;
        })
    )
    .mockResolvedValue(eventSnapshot({ mission_id: 'mission-b' }));
  const hook = renderHook(
    ({ mission }) => useOperatorEvents(mission, identity),
    { initialProps: { mission: 'mission-a' }, wrapper: wrapper() }
  );
  await waitFor(() => expect(get).toHaveBeenCalledTimes(1));
  const signal = get.mock.calls[0][1]!;
  hook.rerender({ mission: 'mission-b' });
  await waitFor(() =>
    expect(hook.result.current.snapshot?.mission_id).toBe('mission-b')
  );
  expect(signal.aborted).toBe(true);
  await act(async () => release(eventSnapshot()));
  expect(hook.result.current.snapshot?.mission_id).toBe('mission-b');
});
it.each([
  [false, 15000],
  [true, 60000],
] as const)(
  'polls with hidden=%s only at its page-level cadence',
  async (hidden, interval) => {
    vi.useFakeTimers();
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(hidden);
    const get = vi
      .spyOn(api, 'readEventSnapshot')
      .mockResolvedValue(eventSnapshot());
    const hook = renderHook(() => useOperatorEvents('mission-a', identity), {
      wrapper: wrapper(),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(get).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(interval - 2);
    });
    expect(get).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(get).toHaveBeenCalledTimes(2);
    hook.unmount();
  }
);
it('quarantines an unreadable pending receipt instead of creating another acknowledgment', async () => {
  sessionStorage.setItem('operator-event-pending:mission-a', '{broken');
  vi.spyOn(api, 'readEventSnapshot').mockResolvedValue(eventSnapshot());
  const post = vi.spyOn(api, 'acknowledgeOperatorEvent');
  const hook = renderHook(() => useOperatorEvents('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  expect(hook.result.current.blocked).toBe(true);
  await act(async () => {
    await hook.result.current.acknowledge(
      hook.result.current.snapshot!.events[0]
    );
  });
  expect(post).not.toHaveBeenCalled();
});
it('creates a valid frozen acknowledgment key on ordinary aircraft HTTP', async () => {
  vi.stubGlobal('crypto', {
    getRandomValues: globalThis.crypto.getRandomValues.bind(globalThis.crypto),
  });
  vi.spyOn(api, 'readEventSnapshot').mockResolvedValue(eventSnapshot());
  const post = vi
    .spyOn(api, 'acknowledgeOperatorEvent')
    .mockRejectedValue(new Error('Lost response'));
  const hook = renderHook(() => useOperatorEvents('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  await act(async () =>
    hook.result.current.acknowledge(hook.result.current.snapshot!.events[0])
  );
  expect(post).toHaveBeenCalledOnce();
  expect(post.mock.calls[0][1]).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
  );
});

it('withholds a foreign epoch snapshot until the same mission source identity is reconciled', async () => {
  const get = vi
    .spyOn(api, 'readEventSnapshot')
    .mockResolvedValue(eventSnapshot({ api_epoch: 'epoch-b' }));
  const post = vi.spyOn(api, 'acknowledgeOperatorEvent');
  const hook = renderHook(
    ({ source }) => useOperatorEvents('mission-a', source),
    { initialProps: { source: identity }, wrapper: wrapper() }
  );
  await waitFor(() => expect(hook.result.current.failed).toBe(true));
  expect(hook.result.current.snapshot).toBeUndefined();
  expect(post).not.toHaveBeenCalled();
  const replacement = JSON.stringify(['store', 'epoch-b', 'live', null]);
  hook.rerender({ source: replacement });
  await waitFor(() =>
    expect(hook.result.current.snapshot?.api_epoch).toBe('epoch-b')
  );
  expect(get).toHaveBeenCalledTimes(2);
  expect(hook.result.current.failed).toBe(false);
  hook.unmount();
});

it('coalesces journal invalidations without canceling an in-flight event refresh', async () => {
  const journalApi = await import('@/services/operator');
  const { useOperatorJournal } = await import('./useOperatorJournal');
  const { health, input, record, page } = await import(
    '@/test/operator-fixtures'
  );
  vi.spyOn(journalApi, 'getOperatorHealth').mockResolvedValue(health);
  vi.spyOn(journalApi, 'readOperatorRecords').mockResolvedValue(page());
  vi.spyOn(journalApi, 'readOperatorRecord').mockResolvedValue(page().items[0]);
  vi.spyOn(journalApi, 'saveOperatorCommand').mockResolvedValue({
    schema_version: 1,
    command_id: 'receipt',
    saved_records: [record],
  });
  const release: (() => void)[] = [];
  const get = vi
    .spyOn(api, 'readEventSnapshot')
    .mockResolvedValueOnce(eventSnapshot())
    .mockImplementation(
      () =>
        new Promise((resolve) => release.push(() => resolve(eventSnapshot())))
    );
  const hook = renderHook(
    () => ({
      events: useOperatorEvents('mission-a', identity),
      journal: useOperatorJournal('mission-a'),
    }),
    { wrapper: wrapper() }
  );
  await waitFor(() =>
    expect(hook.result.current.events.snapshot).toBeDefined()
  );
  await waitFor(() =>
    expect(hook.result.current.journal.health.data?.ready).toBe(true)
  );
  try {
    await act(async () => {
      await hook.result.current.journal.save({
        operation: 'create',
        body: input,
      });
    });
    expect(get).toHaveBeenCalledTimes(2);
    expect(get.mock.calls[1][1]?.aborted).toBe(false);
  } finally {
    await act(async () => {
      release.forEach((resolve) => resolve());
    });
  }
});

const snapshotChanged = () =>
  Object.assign(new Error('Snapshot changed'), {
    response: {
      status: 409,
      data: {
        error: {
          code: 'event_snapshot_changed',
          message: 'Operator state requires reconciliation',
          retryable: true,
        },
      },
    },
  });

it('retries a transient snapshot GET conflict once without sending an acknowledgment', async () => {
  const get = vi
    .spyOn(api, 'readEventSnapshot')
    .mockRejectedValueOnce(snapshotChanged())
    .mockResolvedValue(eventSnapshot());
  const post = vi.spyOn(api, 'acknowledgeOperatorEvent');
  const hook = renderHook(() => useOperatorEvents('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  expect(get).toHaveBeenCalledTimes(2);
  expect(hook.result.current.failed).toBe(false);
  expect(post).not.toHaveBeenCalled();
});

it('bounds snapshot conflict retries and retains the previous snapshot on persistent conflict', async () => {
  const get = vi
    .spyOn(api, 'readEventSnapshot')
    .mockResolvedValueOnce(eventSnapshot())
    .mockRejectedValue(snapshotChanged());
  const hook = renderHook(() => useOperatorEvents('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  act(() => hook.result.current.refresh());
  await waitFor(() => expect(hook.result.current.failed).toBe(true));
  expect(get).toHaveBeenCalledTimes(3);
  expect(hook.result.current.snapshot).toBeDefined();
});
