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
function setFullscreen(active: boolean) {
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    value: active ? document.documentElement : null,
  });
  document.dispatchEvent(new Event('fullscreenchange'));
}
async function send(action: 'recenter' | 'fullscreen') {
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
it('publishes actual fullscreenchange, Escape exit, and heartbeat state', async () => {
  renderHook(() => useOverviewDisplayHost(() => {}));
  await act(Channel.flush);
  act(() => setFullscreen(true));
  await act(Channel.flush);
  expect(snapshot.peers[0].fullscreen).toBe(true);
  act(() => setFullscreen(false));
  await act(Channel.flush);
  expect(snapshot.peers[0].fullscreen).toBe(false);
  // Heartbeats read the document, even before a fullscreenchange notification.
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    value: document.documentElement,
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
    await Channel.flush();
  });
  expect(snapshot.peers[0].fullscreen).toBe(true);
});
it('remote rejection exposes local-click feedback', async () => {
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: async () => {
      throw new TypeError('Denied');
    },
  });
  const host = renderHook(() => useOverviewDisplayHost(() => {}));
  await act(Channel.flush);
  await send('fullscreen');
  expect(host.result.current.fullscreenFeedback).toBe('interaction-required');
  expect(snapshot.feedback?.status).toBe('interaction-required');
});
it('local fullscreen entry clears old rejection so another rejected request after Escape is visible', async () => {
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: async () => {
      throw new TypeError('Denied');
    },
  });
  const host = renderHook(() => useOverviewDisplayHost(() => {}));
  await act(Channel.flush);
  await send('fullscreen');
  expect(host.result.current.fullscreenFeedback).toBe('interaction-required');
  act(() => setFullscreen(true));
  await act(Channel.flush);
  expect(host.result.current.fullscreenFeedback).toBeNull();
  act(() => setFullscreen(false));
  await act(Channel.flush);
  await send('fullscreen');
  expect(host.result.current.fullscreenFeedback).toBe('interaction-required');
});
it('an in-flight native request never replays or reports late success after deadline', async () => {
  let resolve!: () => void;
  const native = vi.fn(
    () =>
      new Promise<void>((done) => {
        resolve = done;
      })
  );
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: native,
  });
  const host = renderHook(() => useOverviewDisplayHost(() => {}));
  await act(Channel.flush);
  await send('fullscreen');
  const command = Channel.sent
    .filter((message) => message.type === 'command')
    .at(-1)!;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
    await Channel.flush();
  });
  expect(snapshot.feedback?.status).toBe('timeout');
  await act(async () => {
    setFullscreen(true);
    resolve();
    await Channel.flush();
  });
  expect(host.result.current.fullscreenFeedback).toBe('expired');
  expect(snapshot.feedback?.status).toBe('timeout');
  expect(snapshot.peers[0].fullscreen).toBe(true);
  const channel = Channel.instances.find(
    (peer) => !peer.closed && peer !== Channel.instances[0]
  )!;
  channel.deliver(command);
  channel.deliver({
    ...command,
    requestId: 'different-expired-request',
    seq: command.seq + 1,
  } as OverviewDisplayMessage);
  await act(Channel.flush);
  expect(native).toHaveBeenCalledTimes(1);
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
