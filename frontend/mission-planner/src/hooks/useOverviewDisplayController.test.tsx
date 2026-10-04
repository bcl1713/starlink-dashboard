/** @vitest-environment jsdom */
import { StrictMode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  createOverviewDisplaySession,
  type OverviewDisplaySession,
} from '@/services/overview-display-session';
import { OverviewTestChannel as Channel } from '@/test/overview-display-channel';
import { useOverviewDisplayController } from './useOverviewDisplayController';

let hosts: OverviewDisplaySession[];
beforeEach(() => {
  vi.useFakeTimers();
  Channel.reset();
  hosts = [];
  vi.stubGlobal('BroadcastChannel', Channel);
});
afterEach(() => {
  cleanup();
  hosts.forEach((host) => host.close());
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
function host() {
  const session = createOverviewDisplaySession({
    role: 'display',
    onSnapshot: () => {},
    readPeer: () => ({
      fullscreen: false,
      actions: ['recenter', 'fullscreen'],
    }),
    onCommand: async () => 'accepted',
  });
  hosts.push(session);
  return session;
}
it('discovers existing displays and sends targeted requests with acknowledged feedback', async () => {
  const display = host();
  const { result } = renderHook(useOverviewDisplayController);
  await act(Channel.flush);
  expect(result.current.peers).toEqual([
    {
      id: display.id,
      label: display.label,
      fullscreen: false,
      actions: ['recenter', 'fullscreen'],
    },
  ]);
  act(() => {
    expect(result.current.send(display.id, 'recenter')).toBeTruthy();
  });
  expect(result.current.feedback?.status).toBe('pending');
  await act(Channel.flush);
  expect(result.current.feedback).toMatchObject({
    targetId: display.id,
    action: 'recenter',
    status: 'accepted',
  });
});
it('no channel and failed channel disable remote requests', async () => {
  vi.stubGlobal('BroadcastChannel', undefined);
  const missing = renderHook(useOverviewDisplayController);
  expect(missing.result.current.available).toBe(false);
  expect(missing.result.current.send('missing', 'recenter')).toBeNull();
  missing.unmount();
  vi.stubGlobal('BroadcastChannel', Channel);
  const display = host();
  const failed = renderHook(useOverviewDisplayController);
  await act(Channel.flush);
  Channel.failPost = true;
  act(() => {
    failed.result.current.send(display.id, 'recenter');
  });
  expect(failed.result.current.available).toBe(false);
  expect(failed.result.current.feedback?.status).toBe('unavailable');
});
it('StrictMode and unmount release channels, listeners, and scheduler', () => {
  const { unmount } = renderHook(useOverviewDisplayController, {
    wrapper: StrictMode,
  });
  expect(Channel.instances.filter((channel) => !channel.closed)).toHaveLength(
    1
  );
  expect(vi.getTimerCount()).toBe(1);
  unmount();
  expect(
    Channel.instances.every(
      (channel) =>
        channel.closed &&
        [...channel.listeners.values()].every((set) => set.size === 0)
    )
  ).toBe(true);
  expect(vi.getTimerCount()).toBe(0);
});
