/** @vitest-environment jsdom */
import { StrictMode } from 'react';
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import {
  createOverviewDisplaySession,
  type OverviewDisplaySession,
} from '@/services/overview-display-session';
import type {
  DisplaySnapshot,
  OverviewDisplayMessage,
} from '@/services/overview-display-protocol';
import { OverviewTestChannel as Channel } from '@/test/overview-display-channel';
import { useOverviewDisplayHost } from './useOverviewDisplayHost';

let controller: OverviewDisplaySession;
let snapshot: DisplaySnapshot;
beforeEach(() => {
  vi.useFakeTimers();
  Channel.reset();
  vi.stubGlobal('BroadcastChannel', Channel);
  controller = createOverviewDisplaySession({
    role: 'controller',
    onSnapshot: (next) => {
      snapshot = next;
    },
  });
});
afterEach(() => {
  cleanup();
  controller.close();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  Reflect.deleteProperty(document, 'fullscreenElement');
  Reflect.deleteProperty(document.documentElement, 'requestFullscreen');
});
async function send(action: 'recenter') {
  act(() => {
    controller.request(snapshot.peers[0].id, action);
  });
  await act(Channel.flush);
}
it('recenter uses the target existing reset callback and latest closure', async () => {
  const old = vi.fn(),
    current = vi.fn();
  const host = renderHook(({ reset }) => useOverviewDisplayHost(reset), {
    initialProps: { reset: old },
  });
  await act(Channel.flush);
  expect(host.result.current.label).toBe(snapshot.peers[0].label);
  host.rerender({ reset: current });
  await send('recenter');
  expect(old).not.toHaveBeenCalled();
  expect(current).toHaveBeenCalledTimes(1);
  expect(snapshot.feedback?.status).toBe('accepted');
  // Acceptance describes callback execution, not settled camera animation.
});
it('advertises recenter only and ignores legacy fullscreen commands', async () => {
  const native = vi.fn();
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: native,
  });
  const reset = vi.fn();
  renderHook(() => useOverviewDisplayHost(reset));
  await act(Channel.flush);
  expect(snapshot.peers[0].actions).toEqual(['recenter']);
  const target = Channel.instances.find(
    (peer) => !peer.closed && peer !== Channel.instances[0]
  )!;
  target.deliver({
    v: 1,
    type: 'command',
    sender: 'legacy',
    target: snapshot.peers[0].id,
    seq: 1,
    requestId: 'fullscreen-old',
    action: 'fullscreen',
    expiresAtMs: Date.now() + 3000,
  } as unknown as OverviewDisplayMessage);
  await act(Channel.flush);
  expect(native).not.toHaveBeenCalled();
  expect(reset).not.toHaveBeenCalled();
});
it('StrictMode unmount removes presence and releases owned resources', async () => {
  const host = renderHook(() => useOverviewDisplayHost(() => {}), {
    wrapper: StrictMode,
  });
  await act(Channel.flush);
  expect(snapshot.peers).toHaveLength(1);
  host.unmount();
  await act(Channel.flush);
  expect(snapshot.peers).toEqual([]);
  expect(vi.getTimerCount()).toBe(1); // Only the controller remains.
  expect(Channel.instances.filter((peer) => !peer.closed)).toHaveLength(1);
});
