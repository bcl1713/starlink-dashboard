/** @vitest-environment jsdom */
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useEventAlerts } from './useEventAlerts';
import * as output from './eventEmitter';
import { eventFixture, eventSnapshot } from '@/test/operator-event-fixtures';
import type { OperatorEventsState } from '@/hooks/api/useOperatorEvents';
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
  localStorage.clear();
});
function state(): OperatorEventsState {
  return {
    snapshot: eventSnapshot(),
    receivedAt: performance.now(),
    failed: false,
    loading: false,
    refreshing: false,
    visible: true,
    refresh: vi.fn(),
    acknowledge: async () => {},
    acknowledging: false,
    pendingAcknowledgment: null,
    retryAcknowledgment: async () => {},
    discardPending: vi.fn(),
    acknowledgmentError: null,
    blocked: false,
    storageWarning: null,
  };
}
it('starts the five-second coalescing window when a new candidate arrives after a quiet period', async () => {
  vi.useFakeTimers({
    toFake: [
      'setTimeout',
      'clearTimeout',
      'setInterval',
      'clearInterval',
      'Date',
      'performance',
    ],
  });
  const create = output.createEventEmitter;
  vi.spyOn(output, 'createEventEmitter').mockImplementation((options) =>
    create({ ...options, claim: async (keys) => keys })
  );
  const hook = renderHook(({ events }) => useEventAlerts(events), {
    initialProps: { events: state() },
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1);
  });
  expect(hook.result.current.batch?.events[0].notification.generation).toBe(
    'occurrence-a'
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(40000);
  });
  const next = eventFixture();
  next.notification = { ...next.notification, generation: 'occurrence-b' };
  hook.rerender({
    events: { ...state(), snapshot: eventSnapshot({ events: [next] }) },
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(hook.result.current.batch?.events[0].notification.generation).toBe(
    'occurrence-a'
  );
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(hook.result.current.batch?.events[0].notification.generation).toBe(
    'occurrence-b'
  );
  hook.unmount();
  expect(vi.getTimerCount()).toBe(0);
});
