// @vitest-environment jsdom

import { act, renderHook } from '@testing-library/react';
import { createRef, StrictMode } from 'react';
import type { PropsWithChildren } from 'react';
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
    assign(element: Element | null) {
      fullscreenElement = element;
    },
    dispatchChange() {
      document.dispatchEvent(new Event('fullscreenchange'));
    },
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
  it('retains one owned entry after platform success until fullscreenchange', async () => {
    const state = installFullscreenState();
    const platform = deferred();
    const root = document.createElement('main');
    root.requestFullscreen = vi.fn(() => platform.promise);
    document.body.append(root);
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const wrapper = ({ children }: PropsWithChildren) => (
      <StrictMode>{children}</StrictMode>
    );
    const { result } = renderHook(() => useOverviewFullscreen(rootRef), {
      wrapper,
    });

    const first = result.current.enter();
    state.assign(root);
    await act(async () => platform.resolve());
    await expect(first).resolves.toBeUndefined();

    const duplicate = result.current.enter();
    expect(duplicate).toBe(first);
    expect(root.requestFullscreen).toHaveBeenCalledOnce();

    act(() => state.dispatchChange());
    expect(result.current.isFullscreen).toBe(true);
  });

  it('consumes native success, restores focus on Escape, and accepts a fresh entry', async () => {
    const state = installFullscreenState();
    const firstPlatform = deferred();
    const secondPlatform = deferred();
    const root = document.createElement('main');
    root.tabIndex = -1;
    root.requestFullscreen = vi
      .fn()
      .mockImplementationOnce(() => firstPlatform.promise)
      .mockImplementationOnce(() => secondPlatform.promise);
    const enterButton = document.createElement('button');
    document.body.append(enterButton, root);
    enterButton.focus();
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    const first = result.current.enter();
    expect(root.requestFullscreen).toHaveBeenCalledOnce();
    expect(result.current.isFullscreen).toBe(false);

    act(() => state.set(root));
    await expect(first).resolves.toBeUndefined();
    expect(result.current.isFullscreen).toBe(true);
    expect(document.activeElement).toBe(root);

    await act(async () => firstPlatform.reject(new Error('late rejection')));
    expect(result.current.error).toBeNull();

    act(() => state.set(null));
    expect(result.current.isFullscreen).toBe(false);
    expect(document.activeElement).toBe(enterButton);

    let second!: Promise<void>;
    act(() => {
      second = result.current.enter();
    });
    expect(root.requestFullscreen).toHaveBeenCalledTimes(2);
    act(() => state.set(root));
    await expect(second).resolves.toBeUndefined();
    secondPlatform.resolve();
  });

  it('consumes one active error outcome and neutralizes its late rejection', async () => {
    installFullscreenState();
    const firstPlatform = deferred();
    const secondPlatform = deferred();
    const root = document.createElement('main');
    const enterButton = document.createElement('button');
    root.requestFullscreen = vi
      .fn()
      .mockImplementationOnce(() => firstPlatform.promise)
      .mockImplementationOnce(() => secondPlatform.promise);
    document.body.append(enterButton, root);
    enterButton.focus();
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    act(() => document.dispatchEvent(new Event('fullscreenerror')));
    expect(result.current.error).toBeNull();

    let first!: Promise<void>;
    let duplicate!: Promise<void>;
    act(() => {
      first = result.current.enter();
      duplicate = result.current.enter();
    });
    expect(first).toBe(duplicate);
    expect(root.requestFullscreen).toHaveBeenCalledOnce();

    act(() => document.dispatchEvent(new Event('fullscreenerror')));
    await expect(first).resolves.toBeUndefined();
    expect(result.current.error).toBe(
      'Fullscreen was unavailable. Use the browser fullscreen control instead.'
    );
    expect(document.activeElement).toBe(enterButton);

    await act(async () => firstPlatform.reject(new Error('late rejection')));
    expect(result.current.error).toBe(
      'Fullscreen was unavailable. Use the browser fullscreen control instead.'
    );

    act(() => document.dispatchEvent(new Event('fullscreenerror')));
    expect(root.requestFullscreen).toHaveBeenCalledOnce();

    let later!: Promise<void>;
    act(() => {
      later = result.current.enter();
      document.dispatchEvent(new Event('fullscreenerror'));
    });
    await expect(later).resolves.toBeUndefined();
    expect(root.requestFullscreen).toHaveBeenCalledTimes(2);
    secondPlatform.reject(new Error('later late rejection'));
  });

  it('consumes a direct platform rejection and keeps entry focus usable', async () => {
    installFullscreenState();
    const root = document.createElement('main');
    const enterButton = document.createElement('button');
    root.requestFullscreen = vi.fn().mockRejectedValue(new Error('denied'));
    document.body.append(enterButton, root);
    enterButton.focus();
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    await act(() => result.current.enter());
    expect(result.current.error).toBe(
      'Fullscreen was unavailable. Use the browser fullscreen control instead.'
    );
    expect(document.activeElement).toBe(enterButton);
  });

  it('keeps other-element state unowned and permits exit retry after rejection', async () => {
    const state = installFullscreenState();
    const root = document.createElement('main');
    const other = document.createElement('aside');
    document.body.append(root, other);
    const exitFullscreen = vi
      .fn()
      .mockRejectedValueOnce(new Error('exit was refused'))
      .mockResolvedValueOnce(undefined);
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

    await act(() => result.current.exit());
    expect(exitFullscreen).toHaveBeenCalledTimes(2);
    expect(result.current.isFullscreen).toBe(true);
    act(() => state.set(null));
    expect(result.current.isFullscreen).toBe(false);
  });

  it('does not request on mount and reports an unsupported API immediately', async () => {
    installFullscreenState();
    const root = document.createElement('main');
    document.body.append(root);
    const rootRef = createRef<HTMLElement>();
    rootRef.current = root;
    const { result } = renderHook(() => useOverviewFullscreen(rootRef));

    expect(root.requestFullscreen).toBeUndefined();
    await act(() => result.current.enter());
    expect(result.current.error).toBe(
      'Fullscreen was unavailable. Use the browser fullscreen control instead.'
    );
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

    let entry!: Promise<void>;
    act(() => {
      entry = result.current.enter();
    });
    unmount();
    await expect(entry).resolves.toBeUndefined();
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
