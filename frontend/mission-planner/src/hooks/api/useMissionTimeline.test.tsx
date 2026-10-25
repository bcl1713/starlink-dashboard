/** @vitest-environment jsdom */
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import * as api from '@/services/missionTimeline';
import { eventSnapshot } from '@/test/operator-event-fixtures';
import { useMissionTimeline } from './useMissionTimeline';

const clients: QueryClient[] = [];
const identity = JSON.stringify(['store', 'epoch-a', 'live', null]);
const snapshot = () => ({ ...eventSnapshot(), legs: [] });
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
afterEach(() => {
  cleanup();
  clients.forEach((c) => c.clear());
  vi.restoreAllMocks();
});
it('cancels a replaced mission and rejects late rows from its old context', async () => {
  let release!: (value: ReturnType<typeof snapshot>) => void;
  const read = vi
    .spyOn(api, 'readMissionTimeline')
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          release = resolve;
        })
    )
    .mockResolvedValue({ ...snapshot(), mission_id: 'mission-b' });
  const hook = renderHook(
    ({ mission }) => useMissionTimeline(mission, identity),
    { initialProps: { mission: 'mission-a' }, wrapper: wrapper() }
  );
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  const signal = read.mock.calls[0][1]!;
  hook.rerender({ mission: 'mission-b' });
  await waitFor(() =>
    expect(hook.result.current.snapshot?.mission_id).toBe('mission-b')
  );
  expect(signal.aborted).toBe(true);
  await act(async () => release(snapshot()));
  expect(hook.result.current.snapshot?.mission_id).toBe('mission-b');
});
it.each([
  'store_id',
  'api_epoch',
  'source_mode',
  'simulation_run_id',
  'mission_id',
] as const)('does not display a snapshot with mismatched %s', async (field) => {
  vi.spyOn(api, 'readMissionTimeline').mockResolvedValue({
    ...snapshot(),
    [field]: field === 'source_mode' ? 'simulation' : 'obsolete',
  });
  const hook = renderHook(() => useMissionTimeline('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.failed).toBe(true));
  expect(hook.result.current.snapshot).toBeUndefined();
});
it('clears cached rows immediately while source identity is unavailable', async () => {
  vi.spyOn(api, 'readMissionTimeline').mockResolvedValue(snapshot());
  const hook = renderHook(
    ({ scope }: { scope: string | null }) =>
      useMissionTimeline('mission-a', scope),
    { initialProps: { scope: identity as string | null }, wrapper: wrapper() }
  );
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  hook.rerender({ scope: null });
  expect(hook.result.current.snapshot).toBeUndefined();
});
it('retains the last validated snapshot on a failed refresh', async () => {
  vi.spyOn(api, 'readMissionTimeline')
    .mockResolvedValueOnce(snapshot())
    .mockRejectedValue(new Error('offline'));
  const hook = renderHook(() => useMissionTimeline('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  act(() => hook.result.current.refresh());
  await waitFor(() => expect(hook.result.current.failed).toBe(true));
  expect(hook.result.current.snapshot?.mission_id).toBe('mission-a');
});

it('removes previously valid rows as soon as a refresh proves the source changed', async () => {
  vi.spyOn(api, 'readMissionTimeline')
    .mockResolvedValueOnce(snapshot())
    .mockResolvedValue({ ...snapshot(), simulation_run_id: 'new-replay' });
  const hook = renderHook(() => useMissionTimeline('mission-a', identity), {
    wrapper: wrapper(),
  });
  await waitFor(() => expect(hook.result.current.snapshot).toBeDefined());
  act(() => hook.result.current.refresh());
  await waitFor(() => expect(hook.result.current.failed).toBe(true));
  expect(hook.result.current.snapshot).toBeUndefined();
});

it.each([false, true])(
  'polls only the visible tab at 15 seconds (hidden=%s)',
  async (hidden) => {
    vi.useFakeTimers();
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(hidden);
    const read = vi
      .spyOn(api, 'readMissionTimeline')
      .mockResolvedValue(snapshot());
    const hook = renderHook(() => useMissionTimeline('mission-a', identity), {
      wrapper: wrapper(),
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(read).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(read).toHaveBeenCalledTimes(hidden ? 1 : 2);
    hook.unmount();
    vi.useRealTimers();
  }
);
