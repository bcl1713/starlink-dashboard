/** @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import * as api from '@/services/operator';
import { failure, health, page, record } from '@/test/operator-fixtures';
import type { RecordPage } from '@/types/operator';
import { operatorIdentity } from './operatorReadSession';
import * as timelineApi from '@/services/missionTimeline';
import * as eventApi from '@/services/operatorEvents';
import { eventSnapshot } from '@/test/operator-event-fixtures';
import { useMissionTimeline } from './useMissionTimeline';
import { useOperatorEvents } from './useOperatorEvents';
import { useWorkspaceRecords } from './useWorkspaceRecords';

const identity = operatorIdentity(health)!;
const clients: QueryClient[] = [];
const snapshot = (rows = [record], H = 1): RecordPage => ({
  ...page(rows),
  H,
  source: { ...health, mission_id: 'mission-a' },
});
function setup() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  clients.push(client);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}
const tick = async (ms = 20) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
});
afterEach(() => {
  cleanup();
  clients.splice(0).forEach((c) => c.clear());
  vi.useRealTimers();
  vi.restoreAllMocks();
});

it('refreshes remote saved versions and passive editor readers without rereading snapshot pages', async () => {
  const baseline = vi
    .spyOn(api, 'readOperatorRecords')
    .mockResolvedValue({ ...snapshot(), cursor: 'fixed-snapshot' });
  let remote = snapshot([], 1);
  const changes = vi
    .spyOn(api, 'readOperatorChanges')
    .mockImplementation(async () => remote);
  const { wrapper } = setup();
  const hook = renderHook(
    () => ({
      owner: useWorkspaceRecords('mission-a', identity),
      editor: useWorkspaceRecords('mission-a', identity, false),
    }),
    { wrapper }
  );
  await tick();
  expect(hook.result.current.owner.items[0].record.version).toBe(1);
  remote = snapshot(
    [
      {
        ...record,
        version: 2,
        journal_seq: 2,
        payload: { ...record.payload, title: 'Other device' },
      },
    ],
    2
  );
  await tick(2050);
  expect(hook.result.current.owner.items[0].record.payload.title).toBe(
    'Other device'
  );
  expect(hook.result.current.editor.items[0].record.version).toBe(2);
  expect(hook.result.current.owner.data?.pages[0].cursor).toBe(
    'fixed-snapshot'
  );
  expect(baseline).toHaveBeenCalledTimes(1);
  expect(changes.mock.calls.length).toBe(2);
});

it('never regresses a newer remote version when an older snapshot refresh finishes', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(snapshot());
  vi.spyOn(api, 'readOperatorChanges').mockResolvedValue(
    snapshot([{ ...record, version: 3, journal_seq: 3 }], 3)
  );
  const { wrapper } = setup();
  const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
    wrapper,
  });
  await tick();
  expect(hook.result.current.items[0].record.version).toBe(3);
  await act(async () => {
    await hook.result.current.refetch();
  });
  await tick();
  expect(hook.result.current.items[0].record.version).toBe(3);
});

it('pauses hidden polling and catches up immediately on visibility and connectivity recovery', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(snapshot());
  let remote = snapshot([], 1);
  const changes = vi
    .spyOn(api, 'readOperatorChanges')
    .mockImplementation(async () => remote);
  const { wrapper } = setup();
  const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
    wrapper,
  });
  await tick();
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
  act(() => document.dispatchEvent(new Event('visibilitychange')));
  const hiddenCount = changes.mock.calls.length;
  remote = snapshot([{ ...record, version: 2, journal_seq: 2 }], 2);
  await tick(10000);
  expect(changes.mock.calls.length).toBe(hiddenCount);
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false);
  act(() => document.dispatchEvent(new Event('visibilitychange')));
  await tick();
  expect(hook.result.current.items[0].record.version).toBe(2);
  changes.mockRejectedValue(new Error('offline'));
  await tick(2050);
  expect(hook.result.current.isError).toBe(true);
  expect(hook.result.current.items[0].record.version).toBe(2);
  changes.mockResolvedValue(
    snapshot([{ ...record, version: 3, journal_seq: 3 }], 3)
  );
  act(() => window.dispatchEvent(new Event('online')));
  await tick();
  expect(hook.result.current.items[0].record.version).toBe(3);
  expect(hook.result.current.isError).toBe(false);
});

it('rebaselines an invalid checkpoint and stops retrying the obsolete watermark', async () => {
  const baseline = vi
    .spyOn(api, 'readOperatorRecords')
    .mockResolvedValueOnce(snapshot())
    .mockResolvedValue(snapshot([], 10));
  const changes = vi
    .spyOn(api, 'readOperatorChanges')
    .mockImplementation(async (_mission, _identity, after) => {
      if (after === 1) throw failure(422, 'validation_error');
      return snapshot([{ ...record, version: 2, journal_seq: 11 }], 11);
    });
  const { wrapper } = setup();
  const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
    wrapper,
  });
  await tick(2100);
  expect(baseline.mock.calls.length).toBe(2);
  expect(changes.mock.calls.filter((c) => c[2] === 1)).toHaveLength(1);
  expect(hook.result.current.items[0].record.version).toBe(2);
});

it.each([
  undefined,
  { ...health, mission_id: 'other-mission' },
  { ...health, api_epoch: 'replaced', mission_id: 'mission-a' },
])(
  'rejects an unproven empty baseline before starting incremental reads (%j)',
  async (source) => {
    vi.spyOn(api, 'readOperatorRecords').mockResolvedValue({
      ...snapshot([], 0),
      source,
    });
    const changes = vi
      .spyOn(api, 'readOperatorChanges')
      .mockResolvedValue(snapshot());
    const { wrapper } = setup();
    const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
      wrapper,
    });
    await tick();
    expect(hook.result.current.items).toEqual([]);
    expect(hook.result.current.isError).toBe(true);
    expect(changes).not.toHaveBeenCalled();
  }
);

it('discards a partial batch when its next page belongs to a replacement context', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(snapshot());
  vi.spyOn(api, 'readOperatorChanges')
    .mockResolvedValueOnce({
      ...snapshot([{ ...record, version: 2 }], 3),
      cursor: 'delta-page-2',
    })
    .mockResolvedValue({
      ...snapshot([{ ...record, version: 3 }], 3),
      source: { ...health, api_epoch: 'replacement', mission_id: 'mission-a' },
    });
  const { wrapper } = setup();
  const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
    wrapper,
  });
  await tick(100);
  expect(
    hook.result.current.items.every((row) => row.record.version === 1)
  ).toBe(true);
  expect(
    hook.result.current.items.some((row) => row.record.version === 2)
  ).toBe(false);
});

it('cancels bootstrap on scope change and ignores its late response', async () => {
  let release!: (page: RecordPage) => void;
  const baseline = vi
    .spyOn(api, 'readOperatorRecords')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve;
        })
    )
    .mockResolvedValue({
      ...snapshot([], 0),
      source: { ...health, mission_id: 'mission-b' },
    });
  vi.spyOn(api, 'readOperatorChanges').mockResolvedValue({
    ...snapshot([], 0),
    source: { ...health, mission_id: 'mission-b' },
  });
  const { wrapper } = setup();
  const hook = renderHook(
    ({ mission }) => useWorkspaceRecords(mission, identity),
    { wrapper, initialProps: { mission: 'mission-a' } }
  );
  await tick();
  const signal = baseline.mock.calls[0][2]?.signal;
  hook.rerender({ mission: 'mission-b' });
  await tick();
  await act(async () => release(snapshot()));
  await tick();
  expect(signal?.aborted).toBe(true);
  expect(hook.result.current.items).toEqual([]);
});

it('removes owned polling and ignores an in-flight batch after unmount', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(snapshot());
  let release!: (page: RecordPage) => void;
  const changes = vi.spyOn(api, 'readOperatorChanges').mockImplementation(
    () =>
      new Promise((resolve) => {
        release = resolve;
      })
  );
  const { wrapper } = setup();
  const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
    wrapper,
  });
  await tick();
  const signal = changes.mock.calls[0][4];
  hook.unmount();
  await act(async () => release(snapshot([{ ...record, version: 2 }], 2)));
  await tick(10000);
  expect(signal?.aborted).toBe(true);
  expect(changes).toHaveBeenCalledTimes(1);
});

it('ignores a late old-epoch batch continuation after a new baseline is active', async () => {
  let release!: (value: RecordPage) => void;
  const nextHealth = { ...health, api_epoch: 'epoch-b' };
  const nextIdentity = operatorIdentity(nextHealth)!;
  vi.spyOn(api, 'readOperatorRecords').mockImplementation(
    async (_filters, _cursor, options) =>
      options?.sourceIdentity === identity
        ? snapshot()
        : {
            ...snapshot([], 0),
            source: { ...nextHealth, mission_id: 'mission-a' },
          }
  );
  const changes = vi
    .spyOn(api, 'readOperatorChanges')
    .mockImplementation(async (_mission, scope, _after, cursor) => {
      if (scope === nextIdentity)
        return {
          ...snapshot([], 0),
          source: { ...nextHealth, mission_id: 'mission-a' },
        };
      if (!cursor)
        return {
          ...snapshot([{ ...record, version: 2 }], 2),
          cursor: 'old-page-2',
        };
      return new Promise((resolve) => {
        release = resolve;
      });
    });
  const { wrapper } = setup();
  const hook = renderHook(
    ({ scope }) => useWorkspaceRecords('mission-a', scope),
    { wrapper, initialProps: { scope: identity } }
  );
  await tick();
  const oldSignal = changes.mock.calls[1][4];
  hook.rerender({ scope: nextIdentity });
  await tick();
  await act(async () => release(snapshot([{ ...record, version: 3 }], 3)));
  await tick();
  expect(oldSignal?.aborted).toBe(true);
  expect(hook.result.current.items).toEqual([]);
  expect(hook.result.current.isError).toBe(false);
});

it('retains the newest displayed snapshot version when later pagination displaces it during a delta outage', async () => {
  vi.spyOn(api, 'readOperatorRecords')
    .mockResolvedValueOnce(snapshot())
    .mockResolvedValueOnce(
      snapshot([{ ...record, version: 3, journal_seq: 3 }], 3)
    )
    .mockResolvedValue({ ...snapshot([], 4), cursor: 'new-snapshot-page-2' });
  const changes = vi
    .spyOn(api, 'readOperatorChanges')
    .mockResolvedValue(
      snapshot([{ ...record, version: 2, journal_seq: 2 }], 2)
    );
  const { wrapper } = setup();
  const hook = renderHook(() => useWorkspaceRecords('mission-a', identity), {
    wrapper,
  });
  await tick();
  expect(hook.result.current.items[0].record.version).toBe(2);
  await act(async () => {
    await hook.result.current.refetch();
  });
  await tick();
  expect(hook.result.current.items[0].record.version).toBe(3);
  changes.mockRejectedValue(new Error('delta unavailable'));
  await act(async () => {
    hook.result.current.refresh();
  });
  await tick();
  await act(async () => {
    await hook.result.current.refetch();
  });
  await tick();
  expect(hook.result.current.data?.pages[0].items).toEqual([]);
  expect(hook.result.current.items[0].record.version).toBe(3);
});

it('keeps shared quarantine until an identity-validated replacement baseline succeeds', async () => {
  const baseline = vi
    .spyOn(api, 'readOperatorRecords')
    .mockResolvedValue(snapshot());
  const changes = vi
    .spyOn(api, 'readOperatorChanges')
    .mockResolvedValue(snapshot([], 1));
  const { wrapper } = setup();
  const hook = renderHook(
    () => ({
      owner: useWorkspaceRecords('mission-a', identity),
      editor: useWorkspaceRecords('mission-a', identity, false),
    }),
    { wrapper }
  );
  await tick();
  baseline.mockRejectedValue(new Error('replacement baseline unavailable'));
  changes.mockRejectedValue(failure(409, 'store_context_changed'));
  act(() => hook.result.current.owner.refresh());
  await tick(2050);
  expect(hook.result.current.owner.data).toBeUndefined();
  expect(hook.result.current.owner.quarantined).toBe(true);
  expect(hook.result.current.editor.quarantined).toBe(true);
  expect(hook.result.current.owner.items).toEqual([]);
  baseline.mockResolvedValue(snapshot([], 0));
  changes.mockResolvedValue(snapshot([], 0));
  act(() => hook.result.current.owner.refresh());
  await tick();
  expect(hook.result.current.owner.quarantined).toBe(false);
  expect(hook.result.current.editor.quarantined).toBe(false);
});

it.each([false, true])(
  'restarts pre-save projections when a delta arrives (cached=%s)',
  async (cached) => {
    vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(snapshot());
    let remote = snapshot([], 1);
    vi.spyOn(api, 'readOperatorChanges').mockImplementation(async () => remote);
    let releaseTimeline!: (
      value: ReturnType<typeof eventSnapshot> & { legs: [] }
    ) => void;
    let releaseEvents!: (value: ReturnType<typeof eventSnapshot>) => void;
    const old = eventSnapshot();
    const fresh = eventSnapshot({ H: 2, events: [] });
    const timeline = vi.spyOn(timelineApi, 'readMissionTimeline');
    const events = vi.spyOn(eventApi, 'readEventSnapshot');
    if (cached) {
      timeline.mockResolvedValueOnce({ ...old, legs: [] });
      events.mockResolvedValueOnce(old);
    }
    timeline
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            releaseTimeline = resolve;
          })
      )
      .mockResolvedValue({ ...fresh, legs: [] });
    events
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            releaseEvents = resolve;
          })
      )
      .mockResolvedValue(fresh);
    const { client, wrapper } = setup();
    const hook = renderHook(
      () => ({
        records: useWorkspaceRecords('mission-a', identity),
        timeline: useMissionTimeline('mission-a', identity),
        events: useOperatorEvents('mission-a', identity),
      }),
      { wrapper }
    );
    await tick();
    if (cached) {
      act(() => {
        for (const name of ['mission-timeline', 'operator-events'])
          void client.invalidateQueries({
            queryKey: [name, 'mission-a', identity],
            exact: true,
          });
      });
      await tick();
    }
    remote = snapshot([{ ...record, version: 2, journal_seq: 2 }], 2);
    await tick(2050);
    await act(async () => {
      releaseTimeline({ ...old, legs: [] });
      releaseEvents(old);
    });
    await tick();
    expect(hook.result.current.records.items[0].record.version).toBe(2);
    expect(hook.result.current.timeline.snapshot?.H).toBe(2);
    expect(hook.result.current.events.snapshot?.H).toBe(2);
  }
);

it('removes departed membership from retained snapshot/current versions and passive relationships, then permits a newer return', async () => {
  vi.spyOn(api, 'readOperatorRecords').mockResolvedValue(snapshot());
  let remote: RecordPage & {
    departures?: { record_id: string; version: number; journal_seq: number }[];
  } = snapshot([], 1);
  vi.spyOn(api, 'readOperatorChanges').mockImplementation(async () => remote);
  const { wrapper } = setup();
  const hook = renderHook(
    () => ({
      owner: useWorkspaceRecords('mission-a', identity),
      editor: useWorkspaceRecords('mission-a', identity, false),
    }),
    { wrapper }
  );
  await tick();
  expect(hook.result.current.owner.items).toHaveLength(1);
  remote = {
    ...snapshot([], 2),
    departures: [{ record_id: record.record_id, version: 2, journal_seq: 2 }],
  };
  await tick(2050);
  expect(hook.result.current.owner.items).toEqual([]);
  expect(hook.result.current.editor.items).toEqual([]);
  remote = snapshot([], 2);
  await tick(2050);
  expect(hook.result.current.owner.items).toEqual([]);
  remote = snapshot([{ ...record, version: 3, journal_seq: 3 }], 3);
  await tick(2050);
  expect(hook.result.current.owner.items[0].record.version).toBe(3);
  expect(hook.result.current.editor.items[0].record.version).toBe(3);
});
