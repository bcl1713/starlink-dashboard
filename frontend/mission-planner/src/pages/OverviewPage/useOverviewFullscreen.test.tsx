// @vitest-environment jsdom

import { act, renderHook } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useOverviewFullscreen } from './useOverviewFullscreen';

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function installFullscreenState() {
  let fullscreenElement: Element | null = null;
  Object.defineProperty(document, 'fullscreenElement', {
    configurable: true,
    get: () => fullscreenElement,
  });
  return {
    set(element: Element | null) {
      fullscreenElement = element;
      document.dispatchEvent(new Event('fullscreenchange'));
    },
  };
}

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe('useOverviewFullscreen', () => {
  it('uses fullscreenchange as authority and restores entry focus on exit', async () => {
    const state = installFullscreenState();
    const root = document.createElement('main');
    root.tabIndex = -1;
    root.requestFullscreen = vi.fn().mockResolvedValue(undefined);
    const enterButton = document.createElement('button');
    document.body.append(enterButton, root);
    enterButton.focus();
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    await act(() => result.current.enter());
    expect(root.requestFullscreen).toHaveBeenCalledOnce();
    expect(result.current.isFullscreen).toBe(false);

    act(() => state.set(root));
    expect(result.current.isFullscreen).toBe(true);
    expect(document.activeElement).toBe(root);

    act(() => state.set(null));
    expect(result.current.isFullscreen).toBe(false);
    expect(document.activeElement).toBe(enterButton);
  });

  it('coalesces pending entry attempts and exposes a rejected-entry fallback', async () => {
    installFullscreenState();
    const pending = deferred();
    const root = document.createElement('main');
    root.requestFullscreen = vi.fn(() => pending.promise);
    document.body.append(root);
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    let first!: Promise<void>;
    let second!: Promise<void>;
    act(() => {
      first = result.current.enter();
      second = result.current.enter();
      document.dispatchEvent(new Event('fullscreenerror'));
    });
    expect(first).toBe(second);
    expect(root.requestFullscreen).toHaveBeenCalledOnce();
    expect(result.current.error).toBeNull();

    await act(async () => pending.reject(new Error('permission denied')));
    await expect(first).resolves.toBeUndefined();
    expect(result.current.error).toBe(
      'Fullscreen was unavailable. Use the browser fullscreen control instead.'
    );
  });

  it('consumes exit rejection and does not claim another element fullscreen', async () => {
    const state = installFullscreenState();
    const root = document.createElement('main');
    const other = document.createElement('aside');
    document.body.append(root, other);
    const exitFullscreen = vi
      .fn()
      .mockRejectedValue(new Error('exit was refused'));
    Object.defineProperty(document, 'exitFullscreen', {
      configurable: true,
      value: exitFullscreen,
    });
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    act(() => state.set(other));
    expect(result.current.isFullscreen).toBe(false);
    await act(() => result.current.exit());
    expect(exitFullscreen).not.toHaveBeenCalled();

    act(() => state.set(root));
    await act(() => result.current.exit());
    expect(exitFullscreen).toHaveBeenCalledOnce();
    expect(result.current.isFullscreen).toBe(true);
  });

  it('removes listeners and neutralizes late request settlement on unmount', async () => {
    installFullscreenState();
    const pending = deferred();
    const root = document.createElement('main');
    root.requestFullscreen = vi.fn(() => pending.promise);
    document.body.append(root);
    const add = vi.spyOn(document, 'addEventListener');
    const remove = vi.spyOn(document, 'removeEventListener');
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result, unmount } = renderHook(() =>
      useOverviewFullscreen(rootRef)
    );

    act(() => {
      void result.current.enter();
    });
    unmount();
    await act(async () => pending.reject(new Error('late rejection')));

    expect(add).toHaveBeenCalledWith('fullscreenchange', expect.any(Function));
    expect(add).toHaveBeenCalledWith('fullscreenerror', expect.any(Function));
    expect(remove).toHaveBeenCalledWith(
      'fullscreenchange',
      expect.any(Function)
    );
    expect(remove).toHaveBeenCalledWith(
      'fullscreenerror',
      expect.any(Function)
    );
  });
});
